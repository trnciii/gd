_gd(){
  local cur prev words cword split
  if declare -F _init_completion >/dev/null 2>&1; then
    _init_completion -n / || return
  else
    COMPREPLY=()
    _get_comp_words_by_ref -n / cur prev words cword || return
  fi

  case $cword in
    1)
      COMPREPLY=( $(compgen -W 'about mkdir ls trash rm open info auth' -- "$cur") )
      ;;
    *)
      case ${words[1]} in
        auth)
          COMPREPLY=( $(compgen -W 'init reset') )
          ;;
        ls | mkdir | rm | open | info)
          if [[ "$cur" == */* ]]; then
            local realcur=${cur##*/}
            local prefix=${cur%/*}
            COMPREPLY=( $(compgen -W "$(gd ls $prefix)" -P "${prefix}/" -- "$realcur") )
          else
            COMPREPLY=( $(compgen -W "$(gd ls)" -- "$cur") )
          fi

          if declare -F _init_completion >/dev/null 2>&1; then
            compopt -o nospace # not work on mac
          fi
          ;;
        esac
      ;;
  esac
}

complete -F _gd gd
