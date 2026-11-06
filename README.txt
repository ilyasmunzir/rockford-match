MATCH EXPLORER: run it on your own computer
===========================================

You need Python 3 (python.org). One-time setup, in a terminal in this folder:

    pip install pandas openpyxl

Run it:

    python geocode_matches.py my_matches.xlsx --offline

It writes index.html next to your sheet and opens it in your browser.
index.html is a single self-contained file: no internet, no server, no accounts.
Double-click it any time, email it, or put it on a USB drive.
Try it first with the included sample_matches.csv.

Your sheet needs these columns: Year, Last Name, First Name, Program,
Institution, City, State. A student listed twice in the same year (residency
plus a preliminary or transitional year) is shown as one student.

PIN POSITIONS
  --offline   pins sit at each city's center (works with no internet).
  no flag     looks up each hospital once on OpenStreetMap so pins land on the
              real building. Needs internet for that step only, and
              "pip install geopy". Results are saved in geocode_cache.json.
  Fix a pin by hand: add a row to manual_locations.csv
  (Institution,City,State,Latitude,Longitude) and run again.

EDIT THE PAGE TEXT
  Open match-explorer-template.html in any text editor and find the block
  marked EDIT HERE near the top of the script: title, subtitle, and whether to
  show the upload button. Then run the command again to rebuild index.html.
  (You can also edit index.html directly, in the same block.)

UPDATING THE DATA
  Change your sheet and run the command again.
