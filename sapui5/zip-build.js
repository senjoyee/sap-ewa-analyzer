const fs = require('fs');
const path = require('path');
const AdmZip = require('adm-zip');

const distFolder = path.join(__dirname, 'dist');
const zipFile = path.join(__dirname, 'ewa-analyzer-ui.zip');

if (!fs.existsSync(distFolder)) {
    console.error('Dist folder not found!');
    process.exit(1);
}

try {
    const zip = new AdmZip();
    zip.addLocalFolder(distFolder);
    zip.writeZip(zipFile);

    // Move zip to dist folder so mbt can find it
    const targetPath = path.join(distFolder, 'ewa-analyzer-ui.zip');
    if (fs.existsSync(targetPath)) {
        fs.unlinkSync(targetPath);
    }
    fs.renameSync(zipFile, targetPath);

    console.log(`Successfully created and moved to ${targetPath}`);
} catch (e) {
    console.error('Error creating zip:', e);
    process.exit(1);
}
