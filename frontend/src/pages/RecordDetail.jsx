import React, {useEffect,useState} from 'react';
import {Link,useParams} from 'react-router-dom';
import {recordsApi} from '../api/client';
import {ReadableValue} from '../components/CaseEvidence';
import './ReviewCases.css';
export default function RecordDetail(){
  const {kind,recordId}=useParams();const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true);
  useEffect(()=>{let active=true;setData(null);setError('');setLoading(true);recordsApi.detail(kind,recordId).then(r=>{if(active)setData(r.data);}).catch(e=>{if(active)setError(e.response?.status===404?'Not found':'Could not load record.');}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[kind,recordId]);
  return <main className="main-content"><Link to="/review-queue">Review queue</Link><h1>{kind.replaceAll('_',' ')}: {recordId}</h1><p>Current live record. The case evidence snapshot remains unchanged.</p>{loading?<p role="status">Loading record...</p>:error?<p role="alert">{error}</p>:<div className="glass-card evidence-records"><ReadableValue value={data}/></div>}</main>;
}
