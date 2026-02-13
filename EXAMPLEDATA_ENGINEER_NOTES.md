# EXAMPLEDATA.csv — Engineer Notes

This document describes the structure of **EXAMPLEDATA.csv** and how the system uses it so that **most of the data for each post/pole is shown in the map modal** for field and design engineers.

---

## 1. CSV structure (columns)

Each row in the file represents **one distribution line segment** between two buses (poles). The columns are:

| # | CSV column name | Description | Shown in post modal? |
|---|-----------------|-------------|----------------------|
| 1 | **Count** | Row number | No (not stored) |
| 2 | **Primary Distribution Line  Segment ID** | Unique segment identifier (e.g. DXTUNGF2AC001) | Yes |
| 3 | **From_Bus_ID** | Source bus/pole (e.g. P00000000) | Yes |
| 4 | **To_Bus_ID** | Destination bus/pole (e.g. P00000001) | Yes |
| 5 | **Phasing** | Phase configuration (ABCN, CN, BN, AN, etc.) | Yes |
| 6 | **Configuration** | Line configuration (Triangular, Vertical) | Yes |
| 7 | **System Grounding Type** | e.g. Multi-grounded | Yes |
| 8 | **Length (meters)** | Segment length in meters | Yes |
| 9 | **Conductor Type** | e.g. ACSR | Yes |
| 10 | **Conductor Size** | e.g. 4/0, 336.4 | Yes |
| 11 | **Unit (C)** | Conductor unit (AWG, MCM) | Yes |
| 12 | **Strands (C)** | Conductor strands (e.g. 6/1, 26/7) | Yes |
| 13 | **Neutral Wire Type** | e.g. ACSR | Yes |
| 14 | **Neutral Wire Size** | e.g. 2 | Yes |
| 15 | **Unit (NW)** | Neutral wire unit (AWG) | Yes |
| 16 | **Strands (NW)** | Neutral wire strands (e.g. 6/1) | Yes |
| 17 | **Spacing D12 (meters)** | Spacing between conductors 1–2 | Yes |
| 18 | **Spacing D23 (meters)** | Spacing between conductors 2–3 | Yes |
| 19 | **Spacing D13 (meters)** | Spacing between conductors 1–3 | Yes |
| 20 | **Spacing D1n (meters)** | Spacing conductor 1–neutral | Yes |
| 21 | **Spacing D2n (meters)** | Spacing conductor 2–neutral | Yes |
| 22 | **Spacing D3n (meters)** | Spacing conductor 3–neutral | Yes |
| 23 | **Spacing DC1-C2 (meters)** | Spacing DC1–C2 | Yes |
| 24 | **Height H1 (meters)** | Conductor height H1 | Yes |
| 25 | **Height H2 (meters)** | Conductor height H2 | Yes |
| 26 | **Height H3 (meters)** | Conductor height H3 | Yes |
| 27 | **Height Hn (meters)** | Neutral height | Yes |
| 28 | **Earth Resistivity (Ohm-meter)** | Soil resistivity | Yes |
| 29 | **latitude** | Segment end latitude | Yes |
| 30 | **longitude** | Segment end longitude | Yes |

**Summary:** All columns except **Count** are stored and shown in the post modal when you click a pole that has segment data.

---

## 2. How the data appears for engineers

- **Poles on the map** are created from bus IDs (From_Bus_ID, To_Bus_ID) and coordinates (latitude, longitude) when you upload the CSV as “Poles” (raw line format).
- **Segment data** is stored when you import the same (or matching) file via **Distribution lines** bulk import.
- When an engineer **clicks a pole** on the map, the **modal** shows:
  1. **Post details:** name, pole number, status, feeder, meter, **coordinates**.
  2. **Distribution line segment(s) at this pole:** a table with every field above (Primary Distribution Line Segment ID through Latitude/Longitude) for each segment where this pole is either From_Bus or To_Bus.

So **most of the data from each row of EXAMPLEDATA.csv is visible in the modal** for the corresponding pole(s).

---

## 3. Data flow (for implementation reference)

1. **Upload EXAMPLEDATA.csv as “Poles” (raw line):**  
   Creates posts (poles) with `primary_bus_id` = bus ID and coordinates; creates line connections so geometric lines draw on the map.

2. **Upload the same file as “Distribution lines”:**  
   Creates/updates `DistributionLineSegment` rows with all 29 data columns (segment ID, From/To Bus, phasing, configuration, length, conductor, neutral, spacing, height, earth resistivity, latitude, longitude).

3. **Click a pole:**  
   The app loads post details and all segments where `primary_bus_id` = From_Bus_ID or To_Bus_ID and displays them in the modal table.

---

## 4. Typical values (from EXAMPLEDATA)

- **Phasing:** ABCN (3-phase + neutral), CN, BN, AN (single-phase + neutral).
- **Configuration:** Triangular, Vertical.
- **Conductor:** ACSR; sizes 4/0, 336.4 MCM, 2 AWG; strands 6/1, 26/7.
- **Length:** 2 m to 2672 m per segment.
- **Coordinates:** Latitude ~11.25–11.29, Longitude ~124.71–124.75 (example region).

---

## 5. Notes for engineers

- One pole can have **multiple segments** (e.g. one where it is “From” and several where it is “To”). The modal shows **all** such segments, each in its own table.
- **Coordinates** in the modal are the post’s main coordinates and, per segment, the segment’s latitude/longitude from the CSV when available.
- If a pole shows “No segment data,” ensure the distribution lines file has been imported and that the pole’s **Primary Bus ID** matches **From_Bus_ID** or **To_Bus_ID** in the CSV.
- Re-importing the distribution lines CSV will **update** existing segments by Primary Distribution Line Segment ID, so you can refresh data after fixing the source file.

---

*This file was generated for engineers using EXAMPLEDATA.csv with the Leyeco3 map and distribution line system.*
