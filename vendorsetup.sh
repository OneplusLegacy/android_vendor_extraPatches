# Keep directory changes and helper variables out of the caller's lunch shell.
apply_patches() (
    local top patches_path project_dir project_path target patch patch_id subject commit history
    top=$(gettop) || return 1
    [ -n "$top" ] && [ -d "$top" ] || return 1
    top=$(cd "$top" && pwd -P) || return 1
    patches_path="$top/vendor/extraPatches/patches"
    [ -d "$patches_path" ] || return 1

    for project_dir in "$patches_path"/*; do
        [ -d "$project_dir" ] || continue
        project_path=${project_dir##*/}
        project_path=${project_path//,/\/}
        target="$top/$project_path"
        if [ ! -d "$target" ] ||
                [ "$(git -C "$target" rev-parse --show-toplevel 2>/dev/null)" != "$target" ]; then
            echo "Patch target is not a repository: $project_path" >&2
            return 1
        fi
        cd "$target" || return 1
        if [ -d "$(git rev-parse --git-path rebase-apply)" ] ||
                [ -d "$(git rev-parse --git-path rebase-merge)" ]; then
            echo "Finish the existing am/rebase in $project_path before applying patches." >&2
            return 1
        fi
        if ! git diff --quiet || ! git diff --cached --quiet; then
            echo "Commit or stash tracked changes in $project_path before applying patches." >&2
            return 1
        fi
        history=$(git log -256 --no-merges --format='%H %s') || return 1
        for patch in "$project_dir"/*.patch; do
            [ -f "$patch" ] || continue
            if git apply --reverse --check "$patch" 2>/dev/null; then
                echo "Already applied: $project_path/${patch##*/}"
                continue
            fi
            # Later patches can change an earlier patch's context, making the
            # reverse check fail. Match its actual diff in recent history too.
            subject=$(awk '
                /^Subject: / { text = substr($0, 10); collecting = 1; next }
                collecting && /^[ \t]/ { sub(/^[ \t]+/, ""); text = text " " $0; next }
                collecting { exit }
                END { sub(/^\[PATCH[^]]*\][ \t]*/, "", text); print text }
            ' "$patch")
            patch_id=$(git patch-id --stable < "$patch" | awk 'NR == 1 { print $1 }')
            if [ -z "$subject" ] || [ -z "$patch_id" ]; then
                echo "Invalid mail patch: $patch" >&2
                return 1
            fi
            local applied=false candidate_id
            while read -r commit; do
                [ -n "$commit" ] || continue
                candidate_id=$(git show --format= "$commit" | git patch-id --stable | awk 'NR == 1 { print $1 }')
                if [ "$candidate_id" = "$patch_id" ]; then
                    applied=true
                    break
                fi
            done < <(printf '%s\n' "$history" | awk -v title="$subject" 'substr($0, index($0, " ") + 1) == title { print $1 }')
            if [ "$applied" = true ]; then
                echo "Already committed: $project_path/${patch##*/}"
                continue
            fi
            echo "Applying: $project_path/${patch##*/}"
            if ! git am --no-gpg-sign "$patch"; then
                echo "Failed to apply $patch; stopping." >&2
                # Only abort the session we started, never a pre-existing one.
                if [ -d "$(git rev-parse --git-path rebase-apply)" ]; then
                    git am --abort || return 1
                fi
                return 1
            fi
        done
    done
)

apply_patches
