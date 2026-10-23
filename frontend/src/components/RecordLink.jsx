import React, { createContext, useContext, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { recordsApi } from '../api/client';
const RecordContext=createContext(null);
const recordKey=(kind,id)=>`${kind}:${id}`;
export function RecordLinksProvider({records,children}) {
  const [availability,setAvailability]=useState({});
  const key=JSON.stringify(records);
  useEffect(()=>{
    let active=true;
    const unique=[...new Map(JSON.parse(key).filter(r=>r.id).map(r=>[recordKey(r.kind,r.id),r])).values()];
    setAvailability({});
    (async()=>{const found={};try {
      for(let i=0;i<unique.length;i+=1000){const result=await recordsApi.lookup(unique.slice(i,i+1000));result.data.forEach(r=>{found[recordKey(r.kind,r.id)]=r.exists;});}
      if(active)setAvailability(found);
    } catch {if(active)setAvailability(Object.fromEntries(unique.map(r=>[recordKey(r.kind,r.id),'error'])));}})();
    return ()=>{active=false;};
  },[key]);
  return <RecordContext.Provider value={availability}>{children}</RecordContext.Provider>;
}
export default function RecordLink({kind,id,knownExists,children}) {
  const availability=useContext(RecordContext);
  const [local,setLocal]=useState();
  useEffect(()=>{let active=true;if(!availability&&knownExists===undefined&&id)recordsApi.lookup([{kind,id:String(id)}]).then(r=>{if(active)setLocal(r.data[0]?.exists);}).catch(()=>{if(active)setLocal('error');});return()=>{active=false;};},[availability,knownExists,kind,id]);
  if(!id)return <span>Record identifier not saved</span>;
  const exists=knownExists??(availability?availability[recordKey(kind,id)]:local);
  if(exists===undefined)return <span>{children||id} · Checking record...</span>;
  if(exists==='error')return <span>{children||id} · Could not verify live record</span>;
  if(!exists)return <span>{children||id} · {kind==='claim'?'Claim not found':'Not found'}</span>;
  return <Link className="record-link" to={kind==='claim'?`/claims/${encodeURIComponent(id)}`:`/records/${kind}/${encodeURIComponent(id)}`}>{children||id}</Link>;
}
