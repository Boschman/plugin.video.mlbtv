// Google Apps Script for the MLB.TV Kodi addon game log.
// Receives watched game updates from the addon and keeps the first sheet
// sorted with the most recent game date at the top.
//
// Setup:
// 1. Open your Google Sheet, go to Extensions > Apps Script and paste this file.
// 2. Deploy > New deployment > type "Web app".
//    - Execute as: Me
//    - Who has access: Anyone
// 3. Copy the web app URL (ends in /exec) into the addon setting
//    "Game log URL (Google Apps Script web app)".

const HEADERS = ['Game date', 'Game', 'Type', 'Status'];

function doGet(e) {
  // ?latest=1 returns the most recently watched game (by game date) as JSON
  if (e && e.parameter && e.parameter.latest === '1') {
    let latest = null;
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    if (sheet.getLastRow() > 1) {
      const row = sheet.getRange(2, 1, 1, HEADERS.length).getDisplayValues()[0];
      latest = { date: row[0], game: row[1], type: row[2], status: row[3] };
    }
    return ContentService.createTextOutput(JSON.stringify({ ok: true, latest: latest }))
      .setMimeType(ContentService.MimeType.JSON);
  }
  return ContentService.createTextOutput('MLB.TV game log endpoint is working.');
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const data = JSON.parse(e.postData.contents);
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    ensureHeader_(sheet);
    const rowIndex = findRow_(sheet, data);
    if (rowIndex > 0) {
      sheet.getRange(rowIndex, 4).setValue(data.status);
    } else {
      sheet.insertRowBefore(2);
      // store as plain text so YYYY-MM-DD dates keep sorting correctly
      const range = sheet.getRange(2, 1, 1, HEADERS.length);
      range.setNumberFormat('@');
      range.setValues([[data.date, data.game, data.type, data.status]]);
      sortLog_(sheet);
    }
    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

function ensureHeader_(sheet) {
  if (sheet.getRange(1, 1).getValue() !== HEADERS[0]) {
    sheet.insertRowBefore(1);
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]).setFontWeight('bold');
  }
}

// one row per game date + game + type, so doubleheader games with
// a "(Game N)" suffix get their own rows
function findRow_(sheet, data) {
  const rows = sheet.getDataRange().getDisplayValues();
  for (let i = 1; i < rows.length; i++) {
    if (rows[i][0] === data.date && rows[i][1] === data.game && rows[i][2] === data.type) {
      return i + 1;
    }
  }
  return -1;
}

function sortLog_(sheet) {
  if (sheet.getLastRow() > 2) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, HEADERS.length).sort({ column: 1, ascending: false });
  }
}
