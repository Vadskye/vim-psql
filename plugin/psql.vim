" psql.vim - Database connection to Postgres databases
" Author: Kevin Johnson <vadskye@gmail.com>

" if vi compatible mode is set, don't load
if &cp || exists('g:loaded_psql')
    finish
endif

let g:psql_python_flavor = has('python3') ? 'python3' : has('python') ? 'python' : "none"

" Psql requires Python to work
if g:psql_python_flavor == "none"
    if get(g:, 'psql_warn_python', 1)
        echohl WarningMsg
        echomsg 'Psql: No Python detected'
        echohl None
    endif
    finish
endif
let g:loaded_psql = 1

" Set a variable's default value, but don't override any existing value
" This allows user settings in the vimrc to work
function! s:init_variable(variable_name, value)
    if !exists('g:psql_' . a:variable_name)
        if type(a:value) == type("")
            execute 'let g:psql_' . a:variable_name . ' = "' . a:value . '"'
        elseif type(a:value) == type(0)
                \ || type(a:value) == type([])
                \ || type(a:value) == type({})
            execute 'let g:psql_' . a:variable_name . ' = '. string(a:value)
        else
            echoerr "Unable to recognize type '" . type(a:value) .
                \ "' of '" . string(a:value) .
                \ "' for variable '" . a:variable_name . "'"
        endif
    endif
endfunction


function! s:set_default_options()
    let options = {
        \ 'buffer_name': '__vimpsql__',
        \ 'autoclose': 0,
        \ 'window_size': 10,
    \ }

    for variable_name in keys(options)
        call s:init_variable(variable_name, options[variable_name])
    endfor
endfunction
call s:set_default_options()

" Make sure that all options which should be set by the user have valid values
" Note: there is no actual validation yet, but this can be added later
function! s:validate_options()
    let valid_values = {
    \ }

    for [variable_name, values] in items(valid_values)
        let variable_value = get(g:, 'psql_' . variable_name)
        if ! psql#util_in_list(variable_value, values)
            echohl WarningMsg
            echomsg "Psql: Variable g:psql_" . variable_name . " has invalid value '" . variable_value . "'"
            echohl none
        endif
    endfor
endfunction
call s:validate_options()

nnoremap bs :call psql#exec_paragraph(1)<CR>
nnoremap bS :call psql#exec_paragraph(0)<CR>

autocmd BufEnter,BufRead *.sql call psql#start()
