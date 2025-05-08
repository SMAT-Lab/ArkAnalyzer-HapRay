const AdmZip = require('adm-zip');
const path = require('path');
const fs = require('fs');

function unzipFile(zipFile, output) {
    try {
        const zipPath = path.join(__dirname, '../third-party', zipFile);
        const extractPath = path.join(__dirname, '../third-party', output);
        if (fs.existsSync(extractPath)) {
            return;
        }

        const zip = new AdmZip(zipPath);
        zip.extractAllTo(path.join(__dirname, '../third-party'), true);
    } catch (error) {
        console.log(error);
    }
}

unzipFile('trace_streamer_binary.zip', 'trace_streamer_binary');
