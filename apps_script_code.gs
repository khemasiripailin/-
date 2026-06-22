/**
 * Tutor & Market Tracker backend for Google Sheets.
 * ใช้แทน Service Account JSON / Google Cloud Billing
 *
 * วิธีใช้:
 * 1) เปิด Google Sheet > Extensions > Apps Script
 * 2) วางโค้ดนี้ทั้งหมด
 * 3) แก้ SPREADSHEET_ID และ API_TOKEN ด้านล่าง
 * 4) Deploy > New deployment > Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 5) Copy Web app URL ที่ลงท้ายด้วย /exec ไปใส่ใน Streamlit secrets.toml
 */

const SPREADSHEET_ID = "PASTE_YOUR_GOOGLE_SHEET_ID_HERE";
const API_TOKEN = "change-this-to-any-long-random-text";

const DEFAULT_COLUMNS = {
  teaching_sessions: [
    "id",
    "session_date",
    "day_name",
    "student_name",
    "subject",
    "start_time",
    "end_time",
    "break_minutes",
    "duration_hours",
    "hourly_rate",
    "earning",
    "note",
    "created_at",
  ],
  shopping_runs: ["run_id", "shop_date", "title", "note", "created_at"],
  shopping_items: [
    "item_id",
    "run_id",
    "item_name",
    "category",
    "qty",
    "unit",
    "unit_price",
    "picked",
    "created_at",
  ],
};

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents || "{}");
    if (payload.token !== API_TOKEN) {
      throw new Error("Invalid API token");
    }

    const action = payload.action;
    let data = null;

    if (action === "ensure_tables") {
      ensureTables(payload.columns || DEFAULT_COLUMNS);
      data = true;
    } else if (action === "read_table") {
      data = readTable(payload.table, payload.columns || DEFAULT_COLUMNS[payload.table]);
    } else if (action === "append_row") {
      appendRow(payload.table, payload.columns || DEFAULT_COLUMNS[payload.table], payload.row || {});
      data = true;
    } else if (action === "delete_by_key") {
      deleteByKey(payload.table, payload.columns || DEFAULT_COLUMNS[payload.table], payload.key_col, payload.key_value);
      data = true;
    } else if (action === "update_by_key") {
      updateByKey(payload.table, payload.columns || DEFAULT_COLUMNS[payload.table], payload.key_col, payload.key_value, payload.values || {});
      data = true;
    } else {
      throw new Error("Unknown action: " + action);
    }

    return jsonOutput({ ok: true, data: data });
  } catch (err) {
    return jsonOutput({ ok: false, error: String(err && err.stack ? err.stack : err) });
  }
}

function doGet() {
  return jsonOutput({ ok: true, message: "Tutor & Market Tracker Apps Script backend is running." });
}

function jsonOutput(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function spreadsheet() {
  return SpreadsheetApp.openById(SPREADSHEET_ID);
}

function ensureTables(columnsMap) {
  Object.keys(columnsMap).forEach(function (table) {
    ensureSheet(table, columnsMap[table]);
  });
}

function ensureSheet(table, columns) {
  const ss = spreadsheet();
  let sheet = ss.getSheetByName(table);
  if (!sheet) {
    sheet = ss.insertSheet(table);
  }

  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, columns.length).setValues([columns]);
    sheet.setFrozenRows(1);
    return sheet;
  }

  const lastCol = Math.max(sheet.getLastColumn(), 1);
  const headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0].filter(String);
  if (headers.length === 0) {
    sheet.getRange(1, 1, 1, columns.length).setValues([columns]);
    sheet.setFrozenRows(1);
    return sheet;
  }

  const missing = columns.filter(function (col) {
    return headers.indexOf(col) === -1;
  });
  if (missing.length > 0) {
    sheet.getRange(1, headers.length + 1, 1, missing.length).setValues([missing]);
  }
  sheet.setFrozenRows(1);
  return sheet;
}

function readTable(table, columns) {
  const sheet = ensureSheet(table, columns);
  const lastRow = sheet.getLastRow();
  const lastCol = Math.max(sheet.getLastColumn(), columns.length);
  if (lastRow < 2) return [];

  const values = sheet.getRange(1, 1, lastRow, lastCol).getValues();
  const headers = values[0].map(String);
  const rows = values.slice(1);

  return rows
    .filter(function (row) {
      return row.some(function (cell) {
        return cell !== "";
      });
    })
    .map(function (row) {
      const obj = {};
      headers.forEach(function (header, index) {
        if (header) obj[header] = normalizeCell(row[index]);
      });
      columns.forEach(function (col) {
        if (!(col in obj)) obj[col] = "";
      });
      return obj;
    });
}

function normalizeCell(value) {
  if (Object.prototype.toString.call(value) === "[object Date]") {
    return Utilities.formatDate(value, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
  }
  return value;
}

function appendRow(table, columns, rowObj) {
  const sheet = ensureSheet(table, columns);
  const values = columns.map(function (col) {
    return rowObj[col] !== undefined && rowObj[col] !== null ? rowObj[col] : "";
  });
  sheet.appendRow(values);
}

function deleteByKey(table, columns, keyCol, keyValue) {
  const sheet = ensureSheet(table, columns);
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  const keyIndex = headers.indexOf(keyCol);
  if (keyIndex === -1) throw new Error("Key column not found: " + keyCol);

  const values = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
  for (let i = values.length - 1; i >= 0; i--) {
    if (String(values[i][keyIndex]) === String(keyValue)) {
      sheet.deleteRow(i + 2);
    }
  }
}

function updateByKey(table, columns, keyCol, keyValue, newValues) {
  const sheet = ensureSheet(table, columns);
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;

  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  const keyIndex = headers.indexOf(keyCol);
  if (keyIndex === -1) throw new Error("Key column not found: " + keyCol);

  const values = sheet.getRange(2, 1, lastRow - 1, sheet.getLastColumn()).getValues();
  for (let i = 0; i < values.length; i++) {
    if (String(values[i][keyIndex]) === String(keyValue)) {
      const current = {};
      headers.forEach(function (header, index) {
        if (header) current[header] = values[i][index];
      });
      Object.keys(newValues).forEach(function (key) {
        current[key] = newValues[key];
      });
      const output = headers.map(function (header) {
        return current[header] !== undefined && current[header] !== null ? current[header] : "";
      });
      sheet.getRange(i + 2, 1, 1, headers.length).setValues([output]);
      return;
    }
  }
}
