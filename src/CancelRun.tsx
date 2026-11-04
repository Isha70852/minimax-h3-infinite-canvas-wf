import React from 'react';
export function CancelRun({id,ctx}:any){
 const run=ctx.runs.find((r:any)=>r.node_id===id&&['uploading','submitting','queued','running','reconnecting','downloading'].includes(r.status));
 if(!run)return null;
 return <span className="cancel-run nodrag"><button disabled={!!run.cancel_requested} onClick={()=>ctx.cancel(run.id)}>{run.cancel_requested?'正在取消…':'停止／取消'}</button>{run.cancel_error&&<small className="error-message">{run.cancel_error}</small>}</span>;
}
