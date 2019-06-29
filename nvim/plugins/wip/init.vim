execute "source /home/xbob/config/nvim/init.vim"

" add current dir to runtime path
let &runtimepath.=",".escape(expand("<sfile>:p:h"), "\,")

let g:wip_focus_size = 1
let g:wip_soft_shadow = 1

