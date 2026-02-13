# Complete Data Management Workflow

## Quick Reference: Clean & Import Data

### Step 1️⃣: Clear All Old Data

```powershell
python clear_posts.py
```

When prompted, type **`DELETE`** to confirm.

```
⚠️ CLEARING ALL POSTS AND METER DATA
=========================================

Type 'DELETE' to confirm deletion: DELETE

============================================================
✓ DATABASE CLEARED SUCCESSFULLY
============================================================
✓ Deleted 100 posts
✓ Deleted 200 meter readings

Ready for fresh data import!
============================================================
```

---

### Step 2️⃣: Import New CSV Data

#### Option A: Single CSV file
```powershell
python import_posts_from_csv.py "sample (1).csv"
```

#### Option B: Multiple CSV files at once
```powershell
python import_batch_csv.py "file1.csv" "file2.csv" "file3.csv"
```

#### Option C: All files from a folder
```powershell
python import_batch_csv.py "data/*.csv"
```

#### Expected Output:
```
======================================================================
⚡ BATCH ELECTRICAL POST DATA IMPORTER
======================================================================

📂 Found 2 CSV file(s) to import:

   • file1.csv
   • file2.csv

----------------------------------------------------------------------
✓ file1.csv: 1900 rows, 50 new poles
✓ file2.csv: 1883 rows, 55 new poles

----------------------------------------------------------------------

📊 CONSOLIDATION SUMMARY:
   Total rows processed: 3783
   Total rows skipped: 45
   Total unique poles: 105

📝 Importing 105 poles into database...

  ✓ Added: 81
  ✓ Added: 80
  ✓ Added: 79
  ... (more poles)

======================================================================
✓ IMPORT SUCCESSFUL
======================================================================
✓ Imported 105 new poles
✓ Updated 0 existing poles
✓ Total poles in database: 105
```

---

### Step 3️⃣: Run the Application

```powershell
python app.py
```

Visit: **http://127.0.0.1:5000**

All your new data will be visible on the map! 🗺️

---

## Complete One-Command Workflow

```powershell
# 1. Clear old data
python clear_posts.py

# 2. Import new data (all CSV files)
python import_batch_csv.py "data/*.csv"

# 3. Run app
python app.py
```

Then open: http://127.0.0.1:5000

---

## CSV File Requirements

### Required Columns
Your CSV files must have AT LEAST these columns:
- **Pole Number** (or: pole_number, PoleNumber, pole#)
- **Latitude/Lat** (or: lat, Latitude)
- **Longitude/Long** (or: long, Longitude, lng)

### Optional Columns
These are automatically detected and imported (if present):
- Feeder, Pri. Structure, Phasing, Bus IDs
- kVA Rating, Meter Brand, Serial Number
- Conductor Size, Configuration, etc.

### Column Name Flexibility ✓
Your CSV headers can have:
- ✓ Spaces: `Pole Number`, `Primary Bus ID`
- ✓ Underscores: `pole_number`, `primary_bus_id`
- ✓ Different cases: `POLE NUMBER`, `pole number`
- ✓ Abbreviated: `Lat`, `LAT`, `latitude`

**All variations are automatically detected!** 🎉

---

## Troubleshooting

### "CSV file not found" Error?
✓ Check the exact filename (including spaces)
✓ Use quotes around filenames: `"sample (1).csv"`
✓ Check working directory: `cd c:\Users\Patrick\Downloads\leyeco3\leyeco3`

### Some rows skipped?
✓ Rows are skipped if missing Pole Number
✓ Rows are skipped if Latitude/Longitude are invalid
✓ Check your CSV column headers match expected names

### Database errors?
✓ Ensure MySQL is running (if using MySQL)
✓ Check `.env` DATABASE_URL is correct
✓ Run: `flask db upgrade` to initialize schema

### Want to see all column names?
Edit `import_batch_csv.py` and add after reading CSV:
```python
print("Columns found:", reader.fieldnames)
```

---

## Common Workflows

### Workflow 1: Upload One CSV File Weekly
```powershell
# Step 1: Clear last week's data
python clear_posts.py

# Step 2: Import this week's data
python import_posts_from_csv.py "weekly_data.csv"

# Step 3: Run app
python app.py
```

### Workflow 2: Merge Multiple District Data Files
```powershell
# Step 1: Clear old data
python clear_posts.py

# Step 2: Import all district files at once
python import_batch_csv.py "districts/OBADO.csv" "districts/tamayo.csv" "districts/other.csv"

# Step 3: View consolidated map
python app.py
```

### Workflow 3: Continuous Updates
```powershell
# Skip clearing, just add new data
python import_posts_from_csv.py "new_poles.csv"

# Existing poles update, new poles add
python app.py
```

---

## Data Statistics After Import

After running `python app.py`, you'll see:
- **Poles on Map**: All poles with valid coordinates
- **Transformers**: Complete kVA ratings and phasing
- **Meters**: Brand names and serial numbers tracked
- **Infrastructure**: Full technical specifications visible
- **Service Areas**: Geographic coverage displayed

---

## Next Steps

1. ✅ Clear old data (`clear_posts.py`)
2. ✅ Import new CSV files (`import_batch_csv.py`)
3. ✅ Run application (`python app.py`)
4. 🔄 View complete electrical network on map
5. 📊 Run analytics and reports

---

**That's it! Your electrical distribution network is now digitized and ready for monitoring.** ⚡
