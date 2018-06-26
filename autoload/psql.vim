function s:strip(text)
    return substitute(a:text, '\v^[\n \t]*(.{-})[\n \t]*$', '\1', '')
endfunction

function s:py(cmd)
    execute g:psql_python_flavor . " " . a:cmd
endfunction

function s:pyeval(cmd)
    if g:psql_python_flavor == 'python'
        return pyeval(a:cmd)
    else
        return py3eval(a:cmd)
    endif
endfunction

function psql#start()
    call s:py("import psycopg2 as psy")
endfunction

function psql#exec_paragraph(pretty)
    " make sure the psql window is available
    call psql#open_psql_window()
    " grab the paragraph to execute it
    execute 'normal! "zyip'
    if a:pretty
        call s:py('execute_command("z", True)')
    else
        call s:py('execute_command("z", False)')
    endif
endfunction

function psql#return_to_previous_window()
    execute "normal! \<C-w>p"
endfunction

function! psql#open_psql_window() abort
    let current_line = line('.')
    let file_name = s:get_current_file_name()

    " create the psql window if needed
    if bufwinnr(g:psql_buffer_name) == -1
        call s:create_window()
        call s:configure_window(g:psql_autoclose)
        call psql#return_to_previous_window()
    else
        " if the preview buffer exists, make sure it's configured correctly
    endif
endfunction

" open the psql preview window
function! s:create_window()
    execute "silent keepalt below " . g:psql_window_size . "split " . g:psql_buffer_name
endfunction

" configure the current window to function as a psql window
" this should only be called from within the psql preview window
function! s:configure_window(autoclose) abort
    setlocal noreadonly " in case the 'view' mode is used
    setlocal buftype=nofile
    setlocal bufhidden=hide
    setlocal noswapfile
    setlocal nobuflisted
    " setlocal nomodifiable
    setlocal modifiable
    setlocal nolist
    setlocal nowrap
    setlocal winfixwidth
    setlocal textwidth=0
    setlocal nospell
    " csv is pretty, but painfully slow! This is disabled for now
    if 0 && get(g:, 'loaded_csv')
        " csv file type works well with the vim.csv plugin
        setlocal filetype=csv
        NewDelimiter |
    endif

    let w:autoclose = a:autoclose

    let cpoptions_save = &cpoptions
    set cpoptions&vim

    let &cpoptions = cpoptions_save
endfunction

" Given the name of a buffer, attempt to activate it if it already exists
" return 1 if successfully switched
" return 0 if the buffer does not exist, or if the switch fails
function! s:switch_to_buffer_window(buffer_name)
    if bufexists(a:buffer_name)
        let window_number = bufwinnr(a:buffer_name)
        execute window_number . " wincmd w"
        " if we failed to switch to it, it is probably inactive, so activate it
        if !bufwinnr('') == window_number
            top new
            execute "buffer " . a:name
        endif
        return bufwinnr('') == window_number
    else
        return 0
    endif
endfunction

function! s:get_current_file_name() abort
    let file_name = fnamemodify(bufname('%'), ':p')
    " sending file names with backslashes to python doesn't work properly on
    " windows
    let file_name = substitute(file_name, '\\', '/', 'g')
    return file_name
endfunction

let s:psql_python_path = fnamemodify(expand('<sfile>:p:h'), ':p') . 'psql.py'
if g:psql_python_flavor == 'python'
    execute "pyfile " . s:psql_python_path
else
    execute "py3file " . s:psql_python_path
endif
call s:py('init()')
