#!/usr/bin/env nu

# Process JSON file: apply filter, compress, and clean up intermediate files
# Usage: nu docc.nu <json_filename>
# Example: nu docc.nu "37070344700_Jie Xu_2024_2025.json"

def main [json_file: string] {
    # Check if input file exists
    if not ($json_file | path exists) {
        print $"Error: Input file '($json_file)' does not exist"
        exit 1
    }

    # Parse filename to extract author info
    let filename_stem = ($json_file | path parse | get stem)
    
    # Extract author name and years from filename pattern: "id_Name_startYear_endYear"
    let parts = ($filename_stem | split row "_")
    
    # Determine output filename based on parts
    let output_name = if ($parts | length) < 4 {
        print $"Warning: Filename format doesn't match expected pattern 'id_Name_startYear_endYear'"
        print $"Using simplified output name..."
        $"filtered_($filename_stem).json"
    } else {
        # Extract author name (may contain spaces, so join middle parts)
        let parts_len = ($parts | length)
        let author_parts = ($parts | skip 1 | first ($parts_len - 3))
        let author_name = ($author_parts | str join "_" | str downcase | str replace " " "_")
        let start_year = ($parts | get ($parts_len - 2))
        let end_year = ($parts | get ($parts_len - 1))
        $"($author_name)_($start_year)_($end_year).json"
    }

    print $"Processing: ($json_file)"
    print $"Intermediate file: ($output_name)"

    # Step 1: Apply filter
    print "Step 1: Applying filter..."
    try {
        python main.py filter apply --filter-name only_author_name_in_pub --input $json_file --output $output_name
    } catch { |err|
        print $"Error applying filter: ($err.msg)"
        exit 1
    }

    # Check if intermediate file was created
    if not ($output_name | path exists) {
        print $"Error: Filter step failed - intermediate file '($output_name)' was not created"
        exit 1
    }

    # Step 2: Compress JSON
    print "Step 2: Compressing JSON..."
    try {
        python main.py json compress -i $output_name
    } catch { |err|
        print $"Error compressing JSON: ($err.msg)"
        # Clean up intermediate file even if compression fails
        rm $output_name
        exit 1
    }

    # Step 3: Clean up intermediate file
    print "Step 3: Cleaning up intermediate files..."
    try {
        rm $output_name
        print $"Removed intermediate file: ($output_name)"
    } catch { |err|
        print $"Warning: Failed to remove intermediate file '($output_name)': ($err.msg)"
    }

    # Show final output info
    let compressed_output = $"compress_($output_name | path parse | get stem).json"
    if ($compressed_output | path exists) {
        print $"✓ Processing complete! Output: ($compressed_output)"
    } else {
        print "✓ Processing complete! Check stdout for compressed output."
    }
}
