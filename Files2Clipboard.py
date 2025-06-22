import os
import pyperclip

def Files2Clipboard(path,
                   file_extension=".*",
                   subdirectories=False,
                   technology_filter=None,
                   copy_content=True):
    """
    Copies the directory tree and/or contents of text files within a specified directory
    to the clipboard.

    Version:
        1.3.0
    Parameters:
        - path (str): The path to the directory containing the files.
        - file_extension (str): The file extension to filter files by (e.g., '.txt').
                                Use '.*' to include all files.
        - subdirectories (bool, optional): Whether to include subdirectories in the search.
                                           Defaults to False.
        - technology_filter (dict, optional): A dictionary that filters files based on
                                              technology categories. Defaults to None.
        - copy_content (bool, optional): If False, only the directory tree is copied
                                          (no file contents). If True (default), file
                                          contents are included as well.
    """
    script_name = os.path.basename(__file__)
    content_to_copy = ""

    # Determine which file extensions to include and which directories to exclude
    exts = filter_by_technology(file_extension, technology_filter)
    dir_excludes = filter_directories(technology_filter)

    # If the user only wants the tree, generate and copy it, then exit
    if not copy_content:
        try:
            tree_output = generate_filtered_tree(path, dir_excludes)
            result = f"Directory tree of {path} (filtered):\n{tree_output}"
            pyperclip.copy(result)

            # count the total lines in the result
            total_lines = result.count("\n")
            print(f"Directory tree of {path} (filtered) copied to clipboard [{total_lines} lines].")
        except Exception as e:
            print(f"Could not generate directory tree: {e}")
        return

    # Otherwise, copy_content == True: include tree (if requested) and file contents
    def read_files_in_directory(directory_path, root_label):
        nonlocal content_to_copy
        for fname in os.listdir(directory_path):
            # 1) Never touch the script itself
            if fname == script_name:
                continue

            # 2) Only include files whose extensions made it through the tech filter
            #    (exts is either ".*" or a list of allowed extensions)
            if exts != ".*" and not any(fname.endswith(ext) for ext in exts):
                # fname’s extension isn’t in your filtered list → skip it
                continue

            full_path = os.path.join(directory_path, fname)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    data = f.read()
            except Exception as e:
                print(f"Could not read {full_path} as text: {e}")
                continue

            line_count = data.count("\n") + 1 if data else 0
            content_to_copy += (
                f"{root_label}{fname} ({line_count} lines)\n"
                f"{data}\n\n"
            )
            print(f"Reading file: {full_path} [{line_count} lines]")

    if subdirectories:
        # Prepend the filtered directory tree
        try:
            tree = generate_filtered_tree(path, dir_excludes)
            content_to_copy += f"Directory tree of {path} (filtered):\n{tree}\n\n"
        except Exception as e:
            print(f"Could not generate directory tree: {e}")

        # Walk through subdirectories
        for root, dirs, files in os.walk(path):
            dirs[:] = [
                d for d in dirs
                if d not in ('__pycache__', '.git') + tuple(dir_excludes)
            ]
            label = (
                f"./{os.path.relpath(root, path)}/"
                if root != path else "./"
            )
            read_files_in_directory(root, label)
    else:
        # Only the root directory
        read_files_in_directory(path, "./")

    if content_to_copy:
        pyperclip.copy(content_to_copy)
        total_lines = content_to_copy.count("\n")
        print(f"All contents copied to clipboard [{total_lines} lines].")
    else:
        print("No text files found to copy to clipboard.")


def filter_by_technology(file_extension, technology_filter):
    """
    Adjusts the file extension filter based on the technology filter.
    Returns a list of file extensions to include, or ".*" for all files.
    """
    technology_extensions = {
        'web':             ['.html', '.php', '.js', '.jsx', '.css', '.scss', '.sass'],
        'react':           ['.js', '.jsx', '.ts', '.tsx', '.css', '.scss',
                             '.env', 'package.json', '.babelrc', '.prettierrc'],
        'python':          ['.py'],
        'java':            ['.java'],
        'csharp':          ['.cs'],
        'ruby':            ['.rb'],
        'go':              ['.go'],
        'cpp':             ['.cpp', '.hpp', '.h'],
        'bash':            ['.sh'],
        'typescript':      ['.ts', '.tsx'],
        'rust':            ['.rs', '.toml', '.rlib', '.cargo'],
        'structured-data': ['.yml', '.yaml', '.json'],  # ← newly added
    }

    if technology_filter:
        selected = []
        for tech, enabled in technology_filter.items():
            if enabled and tech in technology_extensions:
                selected.extend(technology_extensions[tech])
        if selected:
            return selected

    return [file_extension] if file_extension != ".*" else ".*"


def filter_directories(technology_filter):
    """
    Returns a list of directory names to exclude from both the tree
    and the content walk.

    Always skips global noise: VCS dirs, IDE settings, caches, build outputs, etc.
    Then adds any tech-specific folders for the enabled flags in technology_filter.
    """
    # 1) global dirs we never want
    global_ignores = {
        # version control
        '.git', '.svn', '.hg', '.bzr',
        # python
        '__pycache__', 'venv', '.venv', 'env', '.egg-info',
        # node / web
        'node_modules', 'bower_components', 'dist', 'build', '.cache',
        # other common outputs
        'target', 'bin', 'obj', 'pkg',
        # logs, tmp, coverage
        'log', 'logs', 'tmp', 'coverage', '.nyc_output',
        # IDE / editor
        '.idea', '.vscode', '.DS_Store',
        # vendor
        'vendor', '.bundle',
    }

    # 2) anything extra per-technology
    tech_specific = {
        'web':             {'public', 'static'},
        'react':           {'public', 'build'},
        'python':          {'dist'},
        'java':            {'build', '.gradle'},
        'csharp':          {'.vs'},
        'ruby':            {'tmp'},
        'go':               {'vendor'},
        'cpp':              set(),
        'bash':             set(),
        'typescript':       set(),
        'rust':             {'target'},
        'structured-data':  set(),  # ← newly added
    }

    excludes = set(global_ignores)
    if technology_filter:
        for tech, enabled in technology_filter.items():
            if enabled:
                excludes.update(tech_specific.get(tech, set()))

    # Return as a list so callers can do: dirs[:] = [d for d in dirs if d not in excludes]
    return list(excludes)


def generate_filtered_tree(root_path, excludes):
    """
    Walks the directory tree from root_path and returns a string representation,
    excluding any directories listed in 'excludes'.
    """
    lines = []
    for current_root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in excludes]
        rel = os.path.relpath(current_root, root_path)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        indent = "│   " * (depth - 1) + ("├── " if depth > 0 else "")
        basename = os.path.basename(current_root) or current_root
        lines.append(f"{indent}{basename}/")
        for i, fname in enumerate(files):
            connector = "└── " if i == len(files) - 1 else "├── "
            lines.append(f"{indent}{connector}{fname}")
    return "\n".join(lines)


if __name__ == "__main__":
    path = os.path.dirname(os.path.abspath(__file__))
    file_extension = ".*"
    subdirectories = True
    technology_filter = {
        'web':             False,
        'react':           False,
        'python':          False,
        'java':            False,
        'rust':            False,
        'cpp':             False,
        'structured-data': True
    }

    # By default, only the directory tree is copied (no file contents).
    Files2Clipboard(path,
                    file_extension=file_extension,
                    subdirectories=subdirectories,
                    technology_filter=technology_filter,
                    copy_content=True)

    # To include file contents as well, set copy_content=True:
    # Files2Clipboard(path, subdirectories=True, technology_filter=technology_filter, copy_content=True)
