from openpyxl import load_workbook
wb = load_workbook("data/climate_dataset_fixed.xlsx", read_only=True)
ws = wb.active
print("Header:", [c.value for c in next(ws.iter_rows(max_row=1))])
print("Sample:", [c.value for c in next(ws.iter_rows(max_row=2))][:6])
