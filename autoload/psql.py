from prettytable import PrettyTable
from pprint import pformat
import psycopg2 as psy
import re
import os
import vim

conn = None
cur = None
vim_buffer_name = '__vimpsql__'
headers = None  # the headers from the most recent query
rows = None  # the rows from the most recent query

show_datetimes = False


def toggle_show_datetimes():
    global show_datetimes
    show_datetimes = not show_datetimes


def init(database_url=None, override=False):
    if not database_url:
        database_url = os.environ["DATABASE_URL"]
    if 'postgres' not in database_url:
        database_url = f"postgres://localhost/{database_url}?sslmode=disable"
    global conn
    global cur
    if conn and not override:
        return
    if get_psql_buffer():
        bprint(f"Connecting to: {database_url}")
    else:
        print(f"Connecting to: {database_url}")
    conn = psy.connect(database_url)
    cur = conn.cursor()


def restart_connection():
    global cur
    conn.rollback()
    cur = conn.cursor()


def get_psql_buffer():
    # find the psql buffer
    for vim_buffer in vim.buffers:
        if re.search(vim_buffer_name, vim_buffer.name):
            return vim.buffers[vim_buffer.number]


def read_register(register):
    """Retrieve the contents of the given vim register

    Args:
        register (str): Address of a vim register

    Yields:
        str: Contents of the register
    """
    return vim.eval('getreg("{}")'.format(register))


def row_to_string(row, is_header=False):
    """Convert a row to a string, mangling times to be more compact

    Args:
        row (tuple): Row of values from a psycopg2 query

    Yields:
        string: Stringified version of the row
    """
    row = list(row)
    for i, val in enumerate(row):
        if not is_header:
            # Quote things that are natively strings
            if isinstance(val, str):
                row[i] = "'{}'".format(val)
        else:
            try:
                row[i] = "<{}>({})".format(
                    type(val).__name__,
                    val.isoformat()
                )
            except AttributeError:
                pass

    joined = "|".join([str(val) for val in row])
    return joined.replace('\n', r'\n')


def parse_row(row):
    row = list(row)
    for i, val in enumerate(row):
        # Quote things that are natively strings
        if isinstance(val, str):
            row[i] = "'{}'".format(val)

        if show_datetimes:
            try:
                row[i] = "<{}>({})".format(
                    type(val).__name__,
                    val.isoformat()
                )
            except AttributeError:
                pass
        else:
            # Reduce size of datetimes
            try:
                row[i] = "<{}>({})".format(
                    type(val).__name__,
                    val.date().isoformat()
                )
            except AttributeError:
                # Reduce size of dates
                try:
                    row[i] = "<{}>({})".format(
                        type(val).__name__,
                        val.isoformat()
                    )
                except AttributeError:
                    pass

        # improve readability of json
        if isinstance(val, dict):
            row[i] = pformat(val)
    return row


is_sql_pattern = re.compile(
    r'\s*(!s|alter|create|delete|drop|insert|select|update|explain|truncate|with|analyze|vacuum|commit|refresh|--)',
    re.IGNORECASE
)


def execute_command(register, pretty=True):
    """Execute an unknown command contained in the given register.
    The command could be either SQL or Python.

    Args:
        register (str): Address of a vim register
    """
    cmd = read_register(register)
    if is_sql_pattern.match(cmd):
        # if we forced it to be sql with !s, strip the !s
        if cmd[:2] == '!s':
            cmd = cmd[2:]
        execute_sql(cmd, pretty)
    else:
        exec(cmd)


create_pattern = re.compile(r'\bcreate\b', re.IGNORECASE)
delete_pattern = re.compile(r'\bdelete\b', re.IGNORECASE)
limit_pattern = re.compile(r'\blimit\b', re.IGNORECASE)
select_pattern = re.compile(r'\bselect\b', re.IGNORECASE)
sql_end_pattern = re.compile(';?\s*$')


def execute_sql(sql, pretty=True):
    """Execute the given SQL

    Args:
        sql (str): SQL to execute
    """
    if 'drop schema' in sql and 'localhost' not in os.environ['DATABASE_URL']:
        raise Exception("Cannot drop schema on nonlocal connection!")
    if (
            select_pattern.search(sql)
            and not (
                limit_pattern.search(sql)
                or create_pattern.search(sql)
                or delete_pattern.search(sql)
            )
    ):
        sql = sql_end_pattern.sub(' limit 200', sql)

    global headers
    global rows
    output = None
    try:
        cur.execute(sql)
    except (psy.NotSupportedError, psy.ProgrammingError, psy.IntegrityError) as e:
        output = str(e).split('\n')
        restart_connection()
    table = None
    if output is None:
        try:
            rows = cur.fetchall()
            headers = cur.description
            if pretty:
                # add the column headers
                table = PrettyTable()
                for desc in cur.description:
                    header = desc[0]
                    table.add_column(header, [], align='l')
                for row in rows:
                    row = parse_row(row)
                    table.add_row(row)
                output = [row_text for row_text in str(table).split('\n')]
            else:
                output = [str([desc[0] for desc in cur.description])]
                for row in rows:
                    output.append(str(parse_row(row)))
            # add a blank line for spacing
            output.append("")
        except psy.ProgrammingError as e:
            conn.commit()
            excerpt = sql.replace('\n', ' ')[:40]
            if len(excerpt) < len(sql):
                excerpt = excerpt.strip() + '...'
            output = '"' + excerpt + '" committed'
    bprint(output)


def bprint(lines, extra_line=True):
    """Display the given input in the psql buffer

    Args:
        text (str or list): Text to display

    Yields:
        type: Explanation
    """
    # if text is a string, convert it to a list for consistency
    if isinstance(lines, str):
        lines = [lines]
    # add a blank line at the end for spacing
    if extra_line and lines[-1] != "":
        lines.append("")

    psql_buffer = get_psql_buffer()
    try:
        psql_buffer.append(lines, 0)
    except Exception as e:
        print(e)


def desc_table(table_name):
    execute_sql("""
        select *
        from information_schema.tables
        where
            table_schema = 'public'
            and table_type='BASE TABLE'
            and table_name = '{}'
    """.format(table_name))


def desc_columns(table_name, order_by=False, full_info=False, extra_where=None):
    order_by_text = 'order by {}'.format(order_by) if order_by else ""
    columns = 'column_name, *' if full_info else 'column_name, data_type'
    where = ["table_name = '{}'".format(table_name)]
    if extra_where:
        where.append(extra_where)
    where_text = ' and '.join(where)
    execute_sql("""
        select {}
        from information_schema.columns
        where {}
        {}
    """.format(columns, where_text, order_by_text))


def desc_fk(table_name):
    execute_sql("""
        SELECT
            tc.constraint_name, tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM
            information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE constraint_type = 'FOREIGN KEY' AND tc.table_name='{}'
    """.format(table_name))


def all_fk():
    execute_sql("""
        SELECT conrelid::regclass AS table_from
              ,conname
              ,pg_get_constraintdef(c.oid)
        FROM   pg_constraint c
        JOIN   pg_namespace n ON n.oid = c.connamespace
        WHERE  contype IN ('f')
        AND    n.nspname = 'public' -- your schema here
        ORDER  BY conrelid::regclass::text, contype DESC;
    """)


def all_tables():
    execute_sql("""
        select table_name from information_schema.tables
        where
            table_schema = 'public'
            and table_type = 'BASE TABLE'
        order by table_name
    """)
