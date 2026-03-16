# Bulk Post Import Guide

## CSV/Excel Format

To import posts using the bulk import feature, create a CSV or Excel file with the following required columns:

### Required Columns:
- **name** - Post identifier/name (e.g., "Pole A", "Post 1")
- **lat** or **latitude** - Latitude coordinate (decimal, e.g., 14.5995)
- **lng** or **longitude** - Longitude coordinate (decimal, e.g., 120.9842)

### Optional Columns:
- **status** - Post status (e.g., "Active", "Inactive")
- **area** - Geographic area/region (e.g., "Manila", "Cebu")

## Example CSV Format:

```csv
name,lat,lng,status,area
Post 1,14.5995,120.9842,Active,Manila
Post 2,14.6091,121.0223,Active,Manila
Pole A,10.2968,123.8854,Inactive,Cebu
```

## Excel Format:

- First row must contain column headers
- Supported Excel files: .xlsx, .xls

## Notes:

1. **Existing posts** with matching names will be **updated** with new coordinates
2. **New posts** with names that don't exist will be **created**
3. **Invalid coordinates** will be skipped with an error message
4. Posts must have valid latitude (-90 to 90) and longitude (-180 to 180)
5. All coordinates must be valid numbers

## Upload Process:

1. Go to **Resources** page (admin only)
2. Click **Choose File** and select your CSV or Excel file
3. Click **Import CSV/Excel**
4. Review the import results
5. The map will automatically reload with the new posts

## Example:

After importing, visit the Electrical Post Data dashboard to see all imported and updated posts.
