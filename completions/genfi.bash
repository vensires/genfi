# Bash completion for genfi

_genfi() {
    local cur prev words cword
    _init_completion || return

    local opts="--version --clean --uninstall --dry-run --force --max-frames --size --frame-position --crop --workers -v --verbose -q --quiet --help"

    case $prev in
        --max-frames|--size|--workers)
            COMPREPLY=()
            return
            ;;
        --frame-position)
            COMPREPLY=()
            return
            ;;
        --crop)
            COMPREPLY=$(compgen -W "fill fit center" -- "$cur")
            return
            ;;
    esac

    if [[ $cur == -* ]]; then
        COMPREPLY=$(compgen -W "$opts" -- "$cur")
    else
        _filedir -d
    fi
} &&
complete -F _genfi genfi
