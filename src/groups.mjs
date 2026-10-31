export function groupNodes(nodes, ids, id) {
 const members=nodes.filter(n=>ids.includes(n.id)&&!n.parentId&&n.data.kind!=='group');
 if(members.length<2)return nodes;
 const x=Math.min(...members.map(n=>n.position.x))-28,y=Math.min(...members.map(n=>n.position.y))-64;
 const right=Math.max(...members.map(n=>n.position.x+(n.measured?.width||Number(n.style?.width)||360)));
 const bottom=Math.max(...members.map(n=>n.position.y+(n.measured?.height||Number(n.style?.height)||260)));
 const chosen=new Set(members.map(n=>n.id));
 return [{id,type:'card',position:{x,y},style:{width:Math.max(420,right-x+28),height:bottom-y+28},dragHandle:'.canvas-group-header',zIndex:-1,data:{kind:'group',label:'群組',collapsed:false},selected:true},...nodes.map(n=>chosen.has(n.id)?{...n,parentId:id,position:{x:n.position.x-x,y:n.position.y-y},selected:false}:{...n,selected:false})];
}
export function ungroupNodes(nodes,id){const group=nodes.find(n=>n.id===id);if(!group)return nodes;return nodes.filter(n=>n.id!==id).map(n=>{if(n.parentId!==id)return n;const {parentId,extent,...rest}=n;return {...rest,position:{x:n.position.x+group.position.x,y:n.position.y+group.position.y},hidden:false};});}
export function arrangeGroup(nodes,id){
 const members=nodes.filter(n=>n.parentId===id),columns=Math.max(1,Math.ceil(Math.sqrt(members.length)));
 const width=Math.max(320,...members.map(n=>n.measured?.width||Number(n.style?.width)||360))+32;
 const height=Math.max(220,...members.map(n=>n.measured?.height||Number(n.style?.height)||260))+40;
 return nodes.map(n=>{const i=members.findIndex(m=>m.id===n.id);if(i>=0)return {...n,position:{x:28+(i%columns)*width,y:64+Math.floor(i/columns)*height}};if(n.id===id)return {...n,style:{...n.style,width:columns*width+24,height:Math.ceil(members.length/columns)*height+64}};return n;});
}
