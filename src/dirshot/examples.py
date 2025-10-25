from src.dirshot.dirshot import *

if __name__ == "__main__":
    # To run a specific example, make sure it is NOT commented out,
    # and the other examples ARE commented out.

    # --- Example 1: Search with NO Presets (Custom Filters) ---
    # Goal: Find the words "API" or "Controller" inside any .java or .js file,
    # while manually ignoring common dependency/build folders.
    # print("\n--- Example 1: Running a custom search with NO presets ---")
    # find_in_project(
    #     root_dir_param="example_project",
    #     output_file_name="search_custom_results.txt",
    #     search_keywords=["API", "Controller"],
        
    #     # --- NO language_presets ---
    #     # Manually define which file types to scan
    #     file_extensions_to_check=[".java", ".js"],
        
    #     # --- NO ignore_presets ---
    #     # Manually define which directories to skip
    #     ignore_dirs_in_path=["node_modules", "build", "venv"],
        
    #     search_file_contents=True,
    #     show_tree_stats=True,
    #     show_token_count=True,
    # )


    # # --- Example 2: Search with Python Presets ---
    # # Goal: Find the word "Flask" inside any Python-related file.
    # # The presets will automatically handle file types and ignore folders like 'venv'.
    # print("\n--- Example 2: Running a search with Python presets ---")
    # find_in_project(
    #     root_dir_param=".",
    #     output_file_name="search_python_preset_results.txt",
    #     search_keywords=[""],
        
    #     # Use presets for convenience
    #     language_presets=[LanguagePreset.PYTHON],
    #     ignore_presets=[IgnorePreset.PYTHON_ENV],
        
    #     search_file_contents=True,
    #     show_tree_stats=True,
    #     show_token_count=True,
    # )


    filter_project(
        root_dir_param=".",
        output_file_name="snapshot.txt",
        file_types=[".py"],
        # Use presets to define the scope of the snapshot
        # language_presets=[LanguagePreset.PYTHON],

        ignore_dirs_in_path=[".git"],
        ignore_presets=[
            IgnorePreset.PYTHON_ENV, 
            IgnorePreset.NODE_MODULES, 
            IgnorePreset.BUILD_ARTIFACTS,
        ],
        
        show_tree_stats=False,
        show_token_count=True,
    )