execute "source /home/xbob/config/nvim/init.vim"

" add current dir to runtime path
let &runtimepath.=",".escape(expand("<sfile>:p:h"), "\,")

hi InsertShadow ctermfg=238 guifg=#444444

let g:wip_hl_group = "InsertShadow"
let g:wip_focus_size = 1

