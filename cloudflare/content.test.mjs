import test from 'node:test';
import assert from 'node:assert/strict';
import { scheduledText, AUTO_REPLIES, autoReply, VOICE_REPLIES, voiceReply } from './content.mjs';
import { handleUpdate } from './worker.mjs';
test('750 mornings and evenings are disjoint and do not repeat', () => {
  const all = new Set(), compliments = new Set();
  for(let i=0;i<750;i++) {
    const date=new Date(Date.parse('2026-09-15T00:00:00Z')+i*86400000).toISOString().slice(0,10);
    const am=scheduledText({key:date+':0'}), pm=scheduledText({key:date+':1'});
    assert.ok(am.startsWith('Доброе утро!')); assert.ok(pm.startsWith('Добрый вечер!'));
    assert.equal(am.match(/Доброе утро!/g).length, 1);
    compliments.add(am.split('\n\n')[0]); all.add(am); all.add(pm);
  }
  assert.equal(all.size,1500); assert.equal(compliments.size,750);
  assert.throws(()=>scheduledText({key:'2026-09-14:0'}));
  assert.throws(()=>scheduledText({key:'2028-10-04:0'}));
});
test('ordinary text and media receive one pool reply without subscribing',async()=>{
  const original=globalThis.fetch; const sent=[];
  globalThis.fetch=async(_,opts)=>{sent.push(JSON.parse(opts.body));return Response.json({ok:true});};
  try {
    for(const body of [{text:'Привет'},{photo:[{file_id:'test'}]},{sticker:{}},{audio:{}},{text:'/unknown'}]) {
      const DB={prepare(){return {bind(){return {async first(){return null;},async run(){}};}};}};
      await handleUpdate({update_id:123,message:{chat:{id:123,type:'private'},...body}},{DB});
    }
    assert.equal(sent.length,5);
    assert.ok(sent.every(x=>AUTO_REPLIES.includes(x.text)));
    await handleUpdate({update_id:124,message:{chat:{id:-1,type:'group'},text:'Привет'}},{});
    assert.equal(sent.length,5);
  } finally { globalThis.fetch=original; }
});
test('voice replies are exact, reachable and used only for voice outside ball mode', async () => {
  assert.deepEqual(VOICE_REPLIES,[
    'Анечка, голосовое принято! Жужа довольно жужужжит 🎧',
    'Ого, сегодня у нас голосовая почта! 💛',
    'Жужа получил голосовое 🤗',
    'Жужа всё слышит, тебе тоже "га-га-га"',
    'Опять переслушивать на репите?',
  ]);
  assert.deepEqual(VOICE_REPLIES.map((_,i)=>voiceReply(()=>(i+0.5)/5)),VOICE_REPLIES);
  assert.equal(voiceReply(()=>0),VOICE_REPLIES[0]);
  assert.equal(voiceReply(()=>1-Number.EPSILON),VOICE_REPLIES.at(-1));
  const original=globalThis.fetch, sent=[];
  let state=null;
  const DB={prepare(){return {bind(){return {async first(){return state;},async run(){}};}};}};
  globalThis.fetch=async(_,opts)=>{sent.push(JSON.parse(opts.body));return Response.json({ok:true});};
  const update={update_id:200,message:{chat:{id:123,type:'private'},voice:{file_id:'test'}}};
  try {
    for(let i=0;i<20;i++) await handleUpdate(update,{DB});
    assert.equal(sent.length,20);
    assert.ok(sent.every(x=>VOICE_REPLIES.includes(x.text)));
    state={awaiting_until:Date.now()+60000,update_id:199};
    await handleUpdate(update,{DB});
    assert.equal(sent.at(-1).text,'🔮 Напиши вопрос текстом. Отменить: /cancel.');
    await handleUpdate({...update,message:{...update.message,chat:{id:-1,type:'group'}}},{});
    assert.equal(sent.length,21);
  } finally {globalThis.fetch=original;}
});
test('random selection can reach all 17 distinct replies including both endpoints', () => {
  assert.equal(AUTO_REPLIES.length,17);
  assert.equal(new Set(AUTO_REPLIES).size,17);
  assert.equal(autoReply(()=>0),AUTO_REPLIES[0]);
  assert.equal(autoReply(()=>1-Number.EPSILON),AUTO_REPLIES.at(-1));
  const selected=AUTO_REPLIES.map((_,i)=>autoReply(()=>(i+0.5)/17));
  assert.deepEqual(selected,AUTO_REPLIES);
  for(let i=0;i<100;i++) assert.ok(AUTO_REPLIES.includes(autoReply()));
});
