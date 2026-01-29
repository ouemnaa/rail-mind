import sharp from 'sharp';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const inputImage = path.join(__dirname, '../public/rail-brain-logo.png');
const outputDir = path.join(__dirname, '../public/icons');

const sizes = [192, 512];

async function generateIcons() {
  for (const size of sizes) {
    const outputPath = path.join(outputDir, `icon-${size}.png`);
    
    await sharp(inputImage)
      .resize(size, size, {
        fit: 'contain',
        background: { r: 255, g: 255, b: 255, alpha: 1 }
      })
      .png()
      .toFile(outputPath);
    
    console.log(`Generated: icon-${size}.png`);
  }
  console.log('All icons generated successfully!');
}

generateIcons().catch(console.error);
