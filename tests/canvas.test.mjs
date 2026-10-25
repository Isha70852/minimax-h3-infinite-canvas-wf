import test from 'node:test';
import assert from 'node:assert/strict';
import {duplicateNode,referenceRows} from '../src/canvas.mjs';
test('duplicate retains both incoming and outgoing neighbors without changing source',()=>{
 const node={id:'g',data:{label:'Generation',spec:{prompt:'one'}},position:{x:100,y:20}};
 const edges=[{id:'e1',source:'a',target:'g',data:{asset_id:'asset'}},{id:'e2',source:'g',target:'b'}];
 const result=duplicateNode(node,edges);
 assert.equal(result.edges[0].source,'a');assert.equal(result.edges[0].target,result.node.id);
 assert.equal(result.edges[1].source,result.node.id);assert.equal(result.edges[1].target,'b');
 result.node.data.spec.prompt='new';assert.equal(node.data.spec.prompt,'one');
 assert.equal(result.edges[0].data.asset_id,'asset');assert.equal(edges[0].target,'g');
});
test('first last order and per-kind ordinals agree with backend',()=>{
 const assets=[{id:'a',kind:'image'},{id:'b',kind:'image'},{id:'s',kind:'audio'}];
 const edges=[{id:'e1',target:'g',data:{asset_id:'b',role:'last'}},{id:'e2',target:'g',data:{asset_id:'s'}},{id:'e3',target:'g',data:{asset_id:'a',role:'first'}}];
 const rows=referenceRows('g',edges,assets);
 assert.deepEqual(rows.map(r=>[r.asset.id,r.alias,r.tag]),[['a','圖片1','<Picture 1>'],['b','圖片2','<Picture 2>'],['s','聲音1','<Audio 1>']]);
});
