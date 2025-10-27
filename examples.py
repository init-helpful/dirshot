# examples.py

# To use these examples, ensure the main script is saved as 'snapshot_generator.py'
# in the same directory as this file. Then, you can uncomment one of the
# examples below and run this script from your terminal:
# python examples.py

from src.dirshot import *

# --- Example 1: Modern Web App (React Frontend + Node.js Backend) ---
# Use Case: Snapshot a full-stack JavaScript project.
# - The `REACT` and `NODE_JS` presets are supersets of `JAVASCRIPT`, automatically
#   including all .js, .ts, .jsx, .tsx, and package.json files.
# - The `NODE_JS` and `IDE_METADATA` ignore presets clean up the most common
#   clutter in web projects (node_modules, IDE configs).

# generate_snapshot(
#     root_directory=".",
#     output_file_name="fullstack_js_snapshot.txt",
#     language_presets=[
#         LanguagePreset.REACT,      # Handles all frontend JS/TS/JSX files
#         LanguagePreset.WEB_FRONTEND  # Includes HTML and CSS files
#     ],
#     ignore_presets=[
#         IgnorePreset.NODE_JS,      # Crucial for ignoring node_modules
#         IgnorePreset.IDE_METADATA, # Superset for .vscode, .idea, etc.
#         IgnorePreset.BUILD_ARTIFACTS,
#         IgnorePreset.VERSION_CONTROL
#     ],
#     generate_tree=True,
#     show_tree_stats=True
# )


# --- Example 2: Mobile App (Native iOS) ---
# Use Case: Capture the source code for a native iOS application.
# - `IOS_NATIVE` is a superset that includes Swift, Objective-C, and key Xcode
#   project files like .storyboard and Info.plist.
# - The `IOS` ignore preset cleans up build folders (DerivedData) and dependency
#   managers (Pods). `IDE_METADATA_XCODE` can also be used for more granularity.

# generate_snapshot(
#     root_directory="./ios_project",
#     output_file_name="ios_native_snapshot.txt",
#     language_presets=[LanguagePreset.IOS_NATIVE],
#     ignore_presets=[
#         IgnorePreset.IOS,
#         IgnorePreset.IDE_METADATA_XCODE,
#         IgnorePreset.VERSION_CONTROL
#     ]
# )


# --- Example 3: Game Development (Unity) ---
# Use Case: Create a snapshot of a Unity game project, focusing on scripts and assets.
# - The `UNITY` language preset is a superset of `C_SHARP` and adds Unity-specific
#   asset files like .unity, .prefab, and .asset.
# - The `UNITY` ignore preset is essential for excluding the large, auto-generated
#   Library, Temp, and Logs folders.

# generate_snapshot(
#     root_directory="./unity_game",
#     output_file_name="unity_game_snapshot.txt",
#     language_presets=[LanguagePreset.UNITY],
#     ignore_presets=[
#         IgnorePreset.UNITY,
#         IgnorePreset.IDE_METADATA, # Ignores .idea, .vscode, etc.
#         IgnorePreset.VERSION_CONTROL
#     ]
# )


# --- Example 4: DevOps & Infrastructure-as-Code (Terraform & Docker) ---
# Use Case: Document the infrastructure configuration for a project.
# - Combines multiple tooling presets (`TERRAFORM`, `DOCKER`, `GITHUB_ACTIONS`)
#   to capture all aspects of the infrastructure and CI/CD pipelines.
# - The `TERRAFORM` ignore preset is critical for excluding state files, which
#   can contain sensitive information.

# generate_snapshot(
#     root_directory="./infra",
#     output_file_name="devops_snapshot.txt",
#     language_presets=[
#         LanguagePreset.TERRAFORM,
#         LanguagePreset.DOCKER,
#         LanguagePreset.GITHUB_ACTIONS,
#         LanguagePreset.BASH # Include helper scripts
#     ],
#     ignore_presets=[
#         IgnorePreset.TERRAFORM,    # Ignore .terraform directory and state files
#         IgnorePreset.SECRET_FILES, # Ignore .env files or credentials
#         IgnorePreset.OS_FILES,
#         IgnorePreset.VERSION_CONTROL
#     ]
# )


# --- Example 5: Data Science Project (Python, Notebooks & SQL) ---
# Use Case: Collate all files from a data analysis or machine learning project.
# - Combines `PYTHON` with `DATA_SCIENCE_NOTEBOOKS` and `SQL` to get a complete
#   picture of the project's logic and queries.
# - `JUPYTER_NOTEBOOKS` and `PYTHON` ignore presets keep the output clean.

# generate_snapshot(
#     root_directory="./data_science_project",
#     output_file_name="data_science_snapshot.txt",
#     language_presets=[
#         LanguagePreset.PYTHON,
#         LanguagePreset.DATA_SCIENCE_NOTEBOOKS, # .ipynb
#         LanguagePreset.SQL,
#         LanguagePreset.MARKUP # Include READMEs
#     ],
#     ignore_presets=[
#         IgnorePreset.PYTHON,             # Ignores venv, __pycache__, etc.
#         IgnorePreset.JUPYTER_NOTEBOOKS,  # Ignores .ipynb_checkpoints
#         IgnorePreset.IDE_METADATA,
#         IgnorePreset.VERSION_CONTROL
#     ]
# )


# --- Example 6: Search for Secrets Across All Config Files ---
# Use Case: Perform a security audit to find hardcoded secrets.
# - Uses the `CONFIGURATION` preset to search only in files like .json, .yml,
#   .toml, and .env.
# - The `search_keywords` list includes common indicators of secrets.
# - The `SECRET_FILES` ignore preset is *omitted* so that .env files are included
#   in the search.

# generate_snapshot(
#     root_directory=".",
#     output_file_name="secrets_audit_results.txt",
#     search_keywords=["password", "secret_key", "api_key", "token"],
#     language_presets=[LanguagePreset.CONFIGURATION],
#     search_file_contents=True,
#     ignore_presets=[
#         IgnorePreset.VERSION_CONTROL,
#         IgnorePreset.NODE_MODULES,
#         IgnorePreset.BUILD_ARTIFACTS
#         # Deliberately not ignoring SECRET_FILES
#     ]
# )


# --- Example 7: "Kitchen Sink" Monorepo Snapshot ---
# Use Case: Snapshot a complex monorepo containing multiple, disparate services.
# - Demonstrates combining presets from completely different ecosystems (Go backend,
#   Svelte frontend, Ansible playbooks) into a single, cohesive output.

# generate_snapshot(
#     root_directory="./monorepo",
#     output_file_name="monorepo_snapshot.txt",
#     language_presets=[
#         LanguagePreset.GO,
#         LanguagePreset.SVELTE,
#         LanguagePreset.DOCKER,
#         LanguagePreset.ANSIBLE,
#         LanguagePreset.MARKUP
#     ],
#     ignore_presets=[
#         IgnorePreset.VERSION_CONTROL,
#         IgnorePreset.IDE_METADATA,
#         IgnorePreset.BUILD_ARTIFACTS,
#         IgnorePreset.NODE_JS, # For the Svelte frontend
#         IgnorePreset.GO      # To ignore Go vendor folders
#     ],
#     generate_tree=True
# )


# --- Main Execution Block ---
# To run an example, uncomment it above and then execute this file.
# The code below runs a basic, safe snapshot as a default.
if __name__ == "__main__":
    print(
        "Welcome to the snapshot generator examples.\n"
        "Please uncomment one of the example calls in this file to run it."
    )
    # As a default, running a general-purpose snapshot on the current directory.
    # This is a good starting point for most projects.
    # generate_snapshot(
    #     root_directory=".",
    #     output_file_name="default_project_snapshot.txt",
    #     language_presets=[
    #         LanguagePreset.PYTHON,
    #         LanguagePreset.JAVASCRIPT,
    #         LanguagePreset.WEB_FRONTEND,
    #         LanguagePreset.DOCKER,
    #         LanguagePreset.MARKUP
    #     ],
    #     ignore_presets=[
    #         IgnorePreset.VERSION_CONTROL,
    #         IgnorePreset.IDE_METADATA,       # The convenient superset
    #         IgnorePreset.BUILD_ARTIFACTS,
    #         IgnorePreset.NODE_JS,
    #         IgnorePreset.PYTHON,
    #         IgnorePreset.OS_FILES,
    #         IgnorePreset.LOGS
    #     ],
    #     generate_tree=True,
    #     show_tree_stats=True,
    #     show_token_count=True,
    # )

    generate_snapshot(
        generate_tree=True,
        ignore_extensions=[".txt"],
        
        ignore_presets=[
            IgnorePreset.IDE_METADATA,
            IgnorePreset.VERSION_CONTROL,
            IgnorePreset.PYTHON,
            IgnorePreset.BUILD_ARTIFACTS,
        ],
        # file_extensions=[".py", ".md", ".json"],
        # show_tree_stats=True,
        # show_token_count=True,
    )
