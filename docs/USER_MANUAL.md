# LEYECO III Grid Analytics — User Manual

> A step-by-step guide for non-technical users on how to use the LEYECO III Power Network Dashboard.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Navigating the System](#2-navigating-the-system)
3. [Using the Map](#3-using-the-map)
4. [Searching for Assets](#4-searching-for-assets)
5. [Inspecting Assets](#5-inspecting-assets)
6. [Uploading Data Files](#6-uploading-data-files-admin-only)
7. [Exporting Data](#7-exporting-data-admin-only)
8. [Managing Uploaded Files](#8-managing-uploaded-files-admin-only)
9. [ML Predictions](#9-ml-predictions)
10. [Account & Settings](#10-account--settings)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Getting Started

### Starting the System (Docker)

To ensure the system runs smoothly on any machine, it is packaged using Docker.

1. Make sure you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running on your computer.
2. Open a terminal or command prompt in the LEYECO III project folder.
3. Run the following command to start the system:
   ```bash
   docker-compose up -d --build
   ```
4. Wait a few moments for the application to start.

### How to Access the System

1. Open your web browser (Google Chrome is recommended).
2. Go to `http://localhost:5000` (or the server URL provided by your administrator).
3. You will see the **Login Page**.

### First Time Setup (Creating an Admin Account)

If this is your first time starting the system and there are no admin accounts yet, the system will automatically show a **Create Admin Account** screen instead of the regular login.

1. You will see a blue welcome banner indicating no admin account exists.
2. Enter your desired **Admin Username** and **Admin Password**.
3. Click **Create Admin & Login**.
4. You will be instantly logged in, and the system will secure itself so no other users can see this setup page.

### Logging In

1. Enter your **Username** and **Password**.
2. Click the **Login** button.
3. You will be redirected to the **Map** page.

> [!NOTE]
> If you do not have an account, ask your system administrator to create one for you. There are two roles:
> - **Admin** — Full access: can upload data, manage files, and manage viewer accounts.
> - **Viewer** — Read-only access: can view the map, search assets, and inspect data.

---

## 2. Navigating the System

The system has a **sidebar** on the left and a **top bar** at the top.

### Sidebar Menu

| Menu Item | Description | Who Can See It |
|---|---|---|
| 🗺️ **Map** | Interactive GIS map showing all poles, lines, and transformers | Everyone |
| ⚡ **Post Data** | Data tables for poles, customers, and line segments | Everyone |
| 📊 **ML Predictions** | Machine learning load stress analysis and predictions | Everyone |
| 👥 **Viewer Accounts** | Manage viewer user accounts | Admin only |
| 📦 **Resources** | Upload, export, and manage network data files | Admin only |

### Expanding/Collapsing the Sidebar

- Click the **☰** hamburger icon at the top of the sidebar to expand or collapse it.
- The sidebar remembers your preference across sessions.

### Top Bar

- The **LEYECO III** logo and title are always visible.
- The 🌙/☀️ button toggles between **light** and **dark mode**.
- Your **username and role** are shown on the top right. Click it to access the **Logout** option.

---

## 3. Using the Map

The **Map** page is the main view of the system. It displays all your distribution network assets on an interactive map.

### Basic Map Controls

| Action | How To Do It |
|---|---|
| **Pan** | Click and drag the map |
| **Zoom In/Out** | Scroll your mouse wheel, or use the `+` / `−` buttons |
| **Click a Pole** | Click any marker on the map to select it and open the Asset Inspector |

### Map Layers

You can toggle different layers on and off using **Map Settings** in the sidebar:

| Layer | What It Shows |
|---|---|
| **Primary Network** | High-voltage feeder lines (color-coded by circuit) |
| **Secondary Network** | Low-voltage lines from transformers to service points |
| **Predicted Lines** | ML-suggested connections for orphaned poles (dashed lines) |   
| **Bus Node Dots** | Blue dots at secondary network junction points |

### Map Settings

Click **Map Settings** in the sidebar (under Map) to access:
- **Layer toggles** — Turn map layers on/off
- **Color customization** — Change the color of primary and secondary lines
- **Visualization options** — Adjust the map display settings

---

## 4. Searching for Assets

The **Search Bar** is located in the top-left corner of the map.

### How to Search

1. Click the **search dropdown** to choose what you want to search for:

| Search Mode | What You Can Find | Example |
|---|---|---|
| **Customer** | Search by Customer ID | `2020010070` |
| **Poles** | Search by Pole Number, Name, or Bus ID | `P0000000108` |
| **Secondary Nodes** | Search by Bus ID, Description, or Pole Number | `S000100-0000003` |
| **Coordinates** | Go to a specific latitude/longitude | `10.42, 124.96` |
| **Connection** | Search by From/To bus connection | `0108→0110` |

2. Type your search query in the text box.
3. A **dropdown list** of matching results will appear.
4. **Click a result** — the map will automatically fly to that location and highlight it.

### Search Tips

- You only need to type a **partial** ID — the system will find matches.
- After selecting a result, the **Asset Inspector** panel on the right will show details.
- Click the **✕** button in the search bar to clear your search.

---

## 5. Inspecting Assets

When you click on any asset (pole, line, transformer) on the map or from search results, the **Asset Inspector** panel opens on the right side.

### What You Can See

| Section | Information Shown |
|---|---|
| **Basic Info** | Pole Number, Name, Feeder, Area, Coordinates |
| **Primary Side** | Bus ID, Conductor Size, Phasing, Configuration |
| **Secondary Side** | Bus ID, Conductor Type, Structure |
| **Transformer** | kVA Rating, Bus ID, Phasing, Grounding |
| **Load Stress** | Utilization %, Load Status, Risk Level, ML Risk Level |
| **Connected Customers** | List of customers served by this transformer |

### Tracing the Network

From the Asset Inspector, you can trace the network:
- **Trace Downstream** — Shows all assets fed by this pole (following electricity flow)
- **Trace Upstream** — Shows the path back to the substation

---

## 6. Uploading Data Files (Admin Only)

> [!IMPORTANT]
> Only **Admin** users can upload data. Viewer accounts do not have access to this feature.

### How to Access the Upload Page

1. Click **Resources** in the sidebar (under the Admin section).
2. The Resources page opens with a **map** and a **sidebar menu** of upload categories.

### Upload Categories

The sidebar on the Resources page is organized into sections. Click each item to open its upload panel:

#### 🗼 Infrastructure (Recommended Order)

| Step | File Type | What It Contains | Required Columns |
|---|---|---|---|
| **Step 1** | 🗺️ Bus Nodes | Electrical bus/node definitions | `Bus ID`, `latitude`, `longitude`, `Bus Description`, `feeder` |
| **Step 2** | 📍 Primary Lines | High-voltage line segments | `From_Bus_ID`, `To_Bus_ID`, `Phasing`, `Length` |
| — | ⚡ Transformers | Distribution transformers | `From Primary Bus ID`, `To Secondary Bus ID`, `kVA Rating` |
| — | 〰️ Secondary Lines | Low-voltage line segments | `From Bus ID`, `To Bus ID`, `Length`, `Phasing` |
| — | 🏠 Service Drops | Customer connections | `From Bus ID`, `To Customer ID`, `Phasing` |

#### 👥 Customer Data

| File Type | What It Contains | Required Columns |
|---|---|---|
| 👥 Customers | Customer master list | `Customer ID`, `Name`, `Customer Type`, `Phase` |
| 📊 Consumption / Billing | Monthly kWh records | `Customer ID`, `Billing Period`, `kWh Consumed` |
| 📈 Load Profiles / Curve | 24-hour load patterns | `Customer Type`, `Hour 1` ... `Hour 24` |

#### ⚙️ Assets

| File Type | Required Columns |
|---|---|
| ⚙️ Voltage Regulators | `From Bus ID`, `To Bus ID`, `Regulated Bus ID`, `kVA Rating` |
| 🔋 Shunt Capacitors | `Bus Connected ID`, `kVAR Rating`, `Voltage Level` |
| 🔌 Shunt Inductors | `Bus Connected ID`, `kVAR Rating`, `Voltage Level` |
| 🔗 Series Inductors | `From Bus ID`, `To Bus ID`, `Inductance (mH)` |

### Step-by-Step: How to Upload a File

1. Go to **Resources** in the sidebar.
2. Expand a category (e.g., **Infrastructure**).
3. Click the specific file type (e.g., **Poles - Step 1**).
4. An **upload panel** will appear on the map.
5. Click **Choose File** and select your `.csv` or `.xlsx` file from your computer.
6. Click the **⬆ Upload** button.
7. Wait for the upload to complete — you will see a **success message** with how many records were imported.

> [!TIP]
> **Not sure about the file format?** Click the **📥 Sample** button next to the Upload button. This will download a sample CSV file showing you the exact format and column names required.

### Upload Order Matters!

> [!WARNING]
> Files should be uploaded **in the correct order** for the system to properly link the data:
> 1. **Bus Nodes** first (provides the electrical nodes AND coordinates for the system)
> 2. **Primary Lines** second (connects buses together)
> 3. Then Transformers, Secondary Lines, Service Drops, Customers, etc.
>
> **Note:** You no longer need to upload separate Pole files if your Bus Nodes or Line files already contain `latitude` and `longitude` coordinates. The system will automatically create the physical infrastructure records for you!

---

## 7. Exporting Data (Admin Only)

### Export Master CSV

1. Go to **Resources** → **Management** → **Master CSV Export**.
2. Click **Export Master CSV**.
3. A comprehensive CSV file will download containing all Posts, Lines, Transformers, Customers, and Consumption data combined into a single flat file.

### Export Network Schematic Image

1. Go to **Resources** → **Management** → **Master CSV Export**.
2. In the **Network Schematic Export** section:
   - Choose **Filter by** (Feeder or Municipality)
   - Select a **Filter value**
   - Choose an **Image size** (HD, 2K, or 4K)
   - Choose a **Line Type** (Primary, Secondary, Both, Predicted, or All)
   - Optionally check **Show Node Points**, **Show Pole Labels**, or **Show Header & Stats**
3. Click **Preview & Download Image**.
4. A preview will appear — click **Download** to save the PNG image.

---

## 8. Managing Uploaded Files (Admin Only)

### View Upload History

1. Go to **Resources** → **Management** → **Manage Files**.
2. You will see a list of all previously uploaded files, including:
   - File type
   - Upload date
   - Number of records imported

### Delete a Specific Upload

1. In the **Manage Files** panel, find the upload you want to remove.
2. Click the **Delete** button next to it.
3. Confirm the deletion — all records from that upload will be removed.

### Delete All Data

> [!CAUTION]
> This action **permanently deletes ALL data** in the system, including all poles, lines, transformers, customers, and related records. IDs will reset to 1. **This cannot be undone.**

1. Go to **Resources** → **Management** → **Delete All Data**.
2. Click **Delete All Data**.
3. A confirmation dialog will appear — click **Confirm** only if you are absolutely sure.

---

## 9. ML Predictions

The **ML Predictions** page shows machine learning analysis of your distribution network.

### What It Shows

- **Transformer Load Stress** — Which transformers are overloaded or at risk
- **Risk Levels** — Color-coded risk assessment (Low, Medium, High, Critical)
- **Predicted Network Links** — Suggested connections for poles that appear disconnected
- **Criticality Scores** — Numerical scores ranking asset importance

### How to Access

1. Click **ML Predictions** in the sidebar.
2. The page displays charts, tables, and statistics about your network health.

---

## 10. Account & Settings

### Changing Theme (Light/Dark Mode)

- Click the **🌙** (moon) or **☀️** (sun) icon in the top-right corner.
- Your preference is saved automatically.

### Logging Out

1. Click your **username** in the top-right corner.
2. Click **Logout**.
3. Confirm by clicking **Logout** in the confirmation dialog.

### Managing Viewer Accounts (Admin Only)

1. Click **Viewer Accounts** in the sidebar (Admin section).
2. You can view all existing viewer accounts.
3. Use the available options to create or manage accounts.

---

## 11. Troubleshooting

> [!WARNING]
> **Don't Panic: "Flying" Secondary Lines**  
> If you see secondary lines "flying" or shooting randomly across the map, this happens because those specific secondary nodes or poles have **not been digitized yet** (they have no GPS coordinates in the system). The system doesn't know where to draw them, so they default to origin points. This is a known data issue, not a system crash. The visuals will automatically correct themselves once the missing physical coordinates are uploaded!

| Problem | Solution |
|---|---|
| **Can't log in** | Check your username and password. Contact your admin if locked out. |
| **Map is blank** | No pole data has been uploaded yet. Ask the admin to upload Poles data first. |
| **Lines are not showing** | Make sure the layer is toggled ON in Map Settings. |
| **"Flying" secondary lines everywhere** | The line connects to a bus node/pole that has no GPS coordinates yet. Upload exact coordinates to fix the mapping. |
| **Upload failed** | Check that your CSV has the correct column headers. Download the Sample file to compare. |
| **Search returns no results** | Try a partial search term. Make sure you selected the correct search mode. |
| **Asset has no location** | The pole coordinates may not have been uploaded. Upload the Poles file first. |
| **"Coordinates missing" message** | The Bus Node or pole is not yet digitized (no GPS coordinates assigned). |
| **System is slow** | Large datasets may take time to load. Try filtering by feeder or municipality. |

---

> **Need help?** Contact your system administrator or the LEYECO III IT department.
