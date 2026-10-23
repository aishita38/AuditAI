import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook} from '@oai/artifact-tool';
import sharp from 'sharp';
const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,'../..');
const out=path.join(root,'data/aster_upload_pack');
const input=JSON.parse(await fs.readFile(path.join(here,'inputs.json'),'utf8'));
await fs.mkdir(path.join(out,'receipts'),{recursive:true});
const quote=v=>{const text=v instanceof Date?v.toISOString():String(v??'');return /[",\r\n]/.test(text)?'"'+text.replaceAll('"','""')+'"':text;};
for(const [name,table] of Object.entries(input.tables)){
  const workbook=Workbook.create();
  const sheet=workbook.worksheets.add('Upload');
  const matrix=[table.headers,...table.rows.map(r=>table.headers.map(k=>r[k]??''))];
  const range=sheet.getRangeByIndexes(0,0,matrix.length,table.headers.length);
  range.values=matrix;
  sheet.getRangeByIndexes(0,0,1,table.headers.length).format={fill:'#253446',font:{bold:true,color:'#FFFFFF'}};
  sheet.getRange('A1:D6').format.columnWidth=25;
  workbook.recalculate();
  const values=range.values;
  if(values.length!==table.rows.length+1)throw new Error('Row count changed: '+name);
  await fs.writeFile(path.join(out,name),values.map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n','utf8');
  const check=await workbook.inspect({kind:'region',sheetId:'Upload',range:'A1:D3',maxChars:400});
  console.log(name,table.rows.length,'rows');
  const preview=await workbook.render({sheetName:'Upload',range:'A1:D6',scale:1,format:'png'});
  await fs.writeFile(path.join(here,name+'.preview.png'),new Uint8Array(await preview.arrayBuffer()));
}
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
for(const r of input.receipts){
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1100"><rect width="1000" height="1100" fill="white"/><g font-family="Arial" fill="#111"><text x="75" y="100" font-size="24">SYNTHETIC ASTER DEMO RECEIPT</text><text x="75" y="190" font-size="34">${esc(r.vendor)}</text><text x="75" y="280" font-size="28">Invoice: ${r.receipt_id}</text><text x="75" y="345" font-size="28">Date: ${r.date}</text><text x="75" y="410" font-size="28">Billed to: Aster Company (demo)</text><path d="M75 460H925" stroke="#333"/><text x="75" y="540" font-size="28">Office supplies and business materials</text><text x="75" y="655" font-size="40">TOTAL INR ${Number(r.amount).toFixed(2)}</text><text x="75" y="745" font-size="28">Paid by bank transfer</text><text x="75" y="880" font-size="24">Upload against claim: ${r.claim_id}</text><text x="75" y="960" font-size="22">Fictional document for testing. Not a tax invoice.</text></g></svg>`;
 await sharp(Buffer.from(svg)).png().toFile(path.join(out,'receipts',r.filename));
}
await fs.writeFile(path.join(out,'ground_truth.json'),JSON.stringify(input.truth,null,2)+'\n');
console.log(out);
