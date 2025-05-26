import os
import pyperclip

def Files2Clipboard(path, file_extension=".*", subdirectories=False, technology_filter=None):
    """
    Copies the contents of text files within a specified directory (and optionally its subdirectories) to the clipboard.

    Version:
        1.0.3
    Parameters:
        - path (str): The path to the directory containing the files.
        - file_extension (str): The file extension to filter files by (e.g., '.txt'). Use '.*' to include all files.
        - subdirectories (bool, optional): Whether to include subdirectories in the search. Defaults to False.
        - technology_filter (dict, optional): A dictionary that filters files based on technology categories. Defaults to None.
    """
    content_to_copy = ""
    script_name = os.path.basename(__file__)  # name of this script file

    # Get filtered extensions and directories based on the technology filter
    file_extension = filter_by_technology(file_extension, technology_filter)
    directory_excludes = filter_directories(technology_filter)

    def read_files_in_directory(directory_path, root_label):
        nonlocal content_to_copy
        for file in os.listdir(directory_path):
            # Skip the script itself
            if file == script_name:
                continue

            if file_extension == ".*" or any(file.endswith(ext) for ext in file_extension):
                file_path = os.path.join(directory_path, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()
                        line_count = file_content.count('\n') + 1 if file_content else 0
                        content_to_copy += (
                            f"{root_label}{file} ({line_count} lines)\n"
                            f"{file_content}\n\n"
                        )
                        print(f"Reading file: {file_path} [{line_count} lines]")
                except Exception as e:
                    print(f"Could not read {file_path} as text: {e}")

    if subdirectories:
        # Run the tree command to get the directory structure
        tree_command = f'tree "{path}" /F'
        try:
            tree_output = os.popen(tree_command).read()
            content_to_copy += f"Directory tree of {path}:\n{tree_output}\n\n"
        except Exception as e:
            print(f"Could not generate directory tree: {e}")

        # Walk through the directory and its subdirectories
        for root, dirs, files in os.walk(path):
            # Filter out unwanted directories
            dirs[:] = [
                d for d in dirs
                if d not in ('__pycache__', '.git') + tuple(directory_excludes)
            ]
            root_label = f"./{os.path.relpath(root, path)}/" if root != path else "./"
            read_files_in_directory(root, root_label)
    else:
        read_files_in_directory(path, "./")

    if content_to_copy:
        pyperclip.copy(content_to_copy)
        total_lines = content_to_copy.count('\n')
        print(f"All contents copied to clipboard [{total_lines} lines].")
    else:
        print("No text files found to copy to clipboard.")

def filter_by_technology(file_extension, technology_filter):
    """
    Adjusts the file extension based on the technology filter.
    Parameters:
    - file_extension (str): The default file extension.
    - technology_filter (dict, optional): A dictionary that filters files based on technologies. Defaults to None.
    
    Returns:
    - A list of file extensions or the original file extension if no filter is applied.
    """
    # Define file extensions for different technologies
    technology_extensions = {
        'web': ['.html', '.php', '.js', '.jsx', '.css', '.scss', '.sass'],
        'react': ['.js', '.jsx', '.ts', '.tsx', '.css', '.scss', '.env', 'package.json', '.babelrc', '.prettierrc'],
        'python': ['.py'],
        'java': ['.java'],
        'csharp': ['.cs'],
        'ruby': ['.rb'],
        'go': ['.go'],
        'cpp': ['.cpp', '.hpp', '.h'],
        'bash': ['.sh'],
        'typescript': ['.ts', '.tsx'],
        'rust': ['.rs', '.toml', '.rlib','.cargo']
    }

    if technology_filter:
        selected_extensions = []
        for tech, enabled in technology_filter.items():
            if enabled and tech in technology_extensions:
                selected_extensions.extend(technology_extensions[tech])
        if selected_extensions:
            return selected_extensions

    return [file_extension] if file_extension != ".*" else ".*"

def filter_directories(technology_filter):
    """
    Returns a list of directory names to exclude based on the technology filter.
    E.g., Rust projects often have a 'target' directory that clutters output.
    """
    tech_directories = {
        'rust': ['target'],
        # you can add other tech-specific directories here, e.g.:
        # 'node': ['node_modules'],
    }

    if technology_filter:
        excluded = []
        for tech, enabled in technology_filter.items():
            if enabled and tech in tech_directories:
                excluded.extend(tech_directories[tech])
        return excluded

    return []

if __name__ == "__main__":
    path = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current file
    file_extension = ".*"  # Use all files by default
    subdirectories = True  # Include subdirectories by default

    # Example dictionary for technology filter
    technology_filter = {
        'web': True,
        'react': False,
        'python': True,
        'java': False,
        'rust': True,
        'cpp': False
    }

    Files2Clipboard(path, file_extension, subdirectories, technology_filter)
