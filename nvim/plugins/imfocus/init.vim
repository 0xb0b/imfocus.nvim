execute "source /home/xbob/config/nvim/init.vim"

" add current dir to runtime path
let &runtimepath.=",".escape(expand("<sfile>:p:h"), "\,")

let g:imfocus_size = 1
let g:imfocus_soft_shadow = 1

