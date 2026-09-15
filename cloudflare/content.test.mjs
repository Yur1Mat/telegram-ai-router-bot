import test from 'node:test';
import assert from 'node:assert/strict';
import { scheduledText, AUTO_REPLY } from './content.mjs';
import { handleUpdate } from './worker.mjs';
test('750 mornings and evenings are disjoint and do not repeat', () => {
  const all = new Set(), compliments = new Set();
  for(let i=0;i<750;i++) {
    const date=new Date(Date.parse('2026-09-15T00:00:00Z')+i*86400000).toISOString().slice(0,10);
    const am=scheduledText({key:date+':0'}), pm=scheduledText({key:date+':1'});
    assert.ok(am.includes('\n\n')); assert.ok(!pm.includes('\n\n'));
    compliments.add(am.split('\n\n')[0]); all.add(am); all.add(pm);
  }
  assert.equal(all.size,1500); assert.equal(compliments.size,750);
  assert.throws(()=>scheduledText({key:'2026-09-14:0'}));
  assert.throws(()=>scheduledText({key:'2028-10-04:0'}));
});
test('ordinary text and media receive the exact reply without subscribing',async()=>{
  const original=globalThis.fetch; const sent=[];
  globalThis.fetch=async(_,opts)=>{sent.push(JSON.parse(opts.body));return Response.json({ok:true});};
  try {
    for(const body of [{text:'Привет'},{photo:[{file_id:'test'}]},{sticker:{}},{voice:{}},{text:'/unknown'}]) {
      await handleUpdate({update_id:123,message:{chat:{id:123,type:'private'},...body}},{});
    }
    assert.equal(sent.length,5);
    assert.ok(sent.every(x=>x.text===AUTO_REPLY));
    assert.equal(AUTO_REPLY,'Ань, я тебе еще не говорил, но ты сегодня такааааая пиздатая!!!');
    await handleUpdate({update_id:124,message:{chat:{id:-1,type:'group'},text:'Привет'}},{});
    assert.equal(sent.length,5);
  } finally { globalThis.fetch=original; }
});
