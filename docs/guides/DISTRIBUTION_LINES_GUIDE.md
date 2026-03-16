# Distribution Line Segments Import Guide

## Overview

The Leyeco3 system now supports importing electrical distribution line segment data with comprehensive technical specifications. Each line segment connects two bus nodes and includes conductor, spacing, and grounding information.

## CSV/Excel Format

### Required Columns
- **segment_id** - Unique identifier for the line segment (e.g., "DXTUNGF2AC001")
- **from_bus_id** - Starting bus ID (e.g., "P00000000")
- **to_bus_id** - Ending bus ID (e.g., "P00000001")

### Optional Columns
- **phasing** - Voltage phasing (e.g., "ABCN", "ABC")
- **configuration** - Line configuration (e.g., "Triangular", "Horizontal", "Vertical Clearance")
- **system_grounding_type** - Grounding method (e.g., "Multi-grounded", "Single-grounded")
- **length_meters** - Length of the line segment in meters
- **conductor_type** - Type of conductor (e.g., "ACSR", "AAC", "AAAC")
- **conductor_size** - Conductor size (e.g., "4/0", "2", "1/0")
- **conductor_unit** - Unit of conductor size (e.g., "AWG", "mm²")
- **conductor_strands** - Strand configuration (e.g., "6/1", "19/1")
- **neutral_wire_type** - Neutral conductor type (e.g., "ACSR", "AAC")
- **neutral_wire_size** - Neutral conductor size (e.g., "2", "4")
- **neutral_wire_unit** - Unit of neutral size (e.g., "AWG")
- **neutral_wire_strands** - Neutral strand configuration (e.g., "6/1")
- **spacing_d12** - Phase-to-phase spacing 1-2 (meters)
- **spacing_d23** - Phase-to-phase spacing 2-3 (meters)
- **spacing_d13** - Phase-to-phase spacing 1-3 (meters)
- **spacing_d1n** - Phase 1 to neutral spacing (meters)
- **spacing_d2n** - Phase 2 to neutral spacing (meters)
- **spacing_d3n** - Phase 3 to neutral spacing (meters)
- **spacing_dc1_c2** - Conductor center-to-center spacing (meters)
- **height_h1** - Height of phase 1 conductor (meters)
- **height_h2** - Height of phase 2 conductor (meters)
- **height_h3** - Height of phase 3 conductor (meters)
- **height_hn** - Height of neutral conductor (meters)
- **earth_resistivity** - Earth resistivity (Ohm-meter)

## Example CSV Data

```csv
segment_id,from_bus_id,to_bus_id,phasing,configuration,system_grounding_type,length_meters,conductor_type,conductor_size,conductor_unit,conductor_strands,neutral_wire_type,neutral_wire_size,neutral_wire_unit,neutral_wire_strands,spacing_d12,spacing_d23,spacing_d13,spacing_d1n,spacing_d2n,spacing_d3n,spacing_dc1_c2,height_h1,height_h2,height_h3,height_hn,earth_resistivity
DXTUNGF2AC001,P00000000,P00000001,ABCN,Triangular,Multi-grounded,80,ACSR,4/0,AWG,6/1,ACSR,2,AWG,6/1,1.383,1.383,2.61,1.475,1.15,1.475,0,8.69,9.15,8.69,8,100
```

## Excel Format

- First row must contain column headers
- Each subsequent row contains one line segment
- Supported file formats: .xlsx, .xls

## How to Import

1. **Prepare Your Data**
   - Create CSV or Excel file with line segment data
   - Ensure all required columns are present
   - Column names are case-insensitive

2. **Go to Resources Page**
   - From the main menu, click "Resources"
   - Scroll to "Bulk Import Distribution Line Segments (CSV/Excel)"

3. **Upload File**
   - Click "Choose File"
   - Select your CSV or Excel file
   - Click "Import CSV/Excel"

4. **Review Results**
   - Successfully imported segments will be displayed with count
   - Any errors will be listed with row numbers
   - Existing segments with matching segment_id will be updated

5. **View in Dashboard**
   - Go to "Electrical Post Data" dashboard
   - New "Distribution Line Segments" table shows all imported segments
   - Search by segment ID, from bus, or to bus ID

## Upsert Behavior

- **New segments** (segment_id not in database) → Created
- **Existing segments** (segment_id already exists) → Updated with new values
- **Invalid rows** → Skipped with error message

## Validation Rules

- All three required fields (segment_id, from_bus_id, to_bus_id) must have values
- Numeric fields (lengths, spacings, heights) must be valid numbers or empty
- Empty optional fields are acceptable

## Integration with Map & Posts

### Bus-to-Post Mapping
Use the bus-to-post mapping to associate line segments with physical post locations:
- Line segments connect bus IDs
- Buses are mapped to posts via the bus_post_mapping table
- When both buses in a segment are mapped to posts with coordinates, they can be visualized on the map

### Map Display
- Distribution lines follow the same bus-to-post mapping as feeder visualization
- Lines appear as connections between mapped posts
- Both buses must have valid coordinates for the line to display

## API Endpoints

### Upload Distribution Lines
```
POST /api/distribution-lines/bulk-import
```
- Admin-only endpoint
- Accepts CSV or Excel file
- Returns: `{ created, updated, skipped, errors }`

### Get All Distribution Lines
```
GET /api/distribution-lines
```
- Returns array of all line segments
- Each segment includes all technical specifications

## Sample Data

A sample file is provided in: `data/sample_distribution_lines.csv`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No file uploaded" | Select a file before clicking Import |
| "File must be CSV or Excel" | Use .csv, .xlsx, or .xls format |
| Invalid number error on row X | Check that numeric fields contain only numbers (e.g., "1.383", not "1.383 m") |
| Segment ID already exists | Update is performed on existing segment - this is normal |

## Example Workflow

1. Export electrical data from your SCADA/engineering system
2. Ensure it includes segment IDs, bus IDs, and technical specs
3. Save as CSV or Excel
4. Go to Resources page
5. Upload file
6. Review import results
7. Navigate to dashboard to view all line segments
8. Use map to visualize lines (after bus-to-post mapping setup)
