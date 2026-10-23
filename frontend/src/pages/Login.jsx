import React, { useState,useEffect } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { LockKeyhole, Mail } from 'lucide-react';
import { isReviewer, useAuth } from '../auth/AuthContext';
import { authApi } from '../api/client';

export default function Login() {
  const { user, login,developerLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [dev,setDev]=useState(null);
  const [challenge,setChallenge]=useState(null);
  const [otp,setOtp]=useState('');
  useEffect(()=>{
    let active=true;
    authApi.devStatus().then(res=>{if(active)setDev(res.data);}).catch(()=>{if(active)setDev({enabled:false});});
    return ()=>{active=false;};
  },[]);

  async function generateOtp() {
    setSubmitting(true);setError('');setChallenge(null);setOtp('');
    try { const result=(await authApi.devGenerate(email)).data;setChallenge(result);setOtp(result.otp); }
    catch(e){setError(e.response?.data?.detail||'Could not generate developer OTP.');}
    finally{setSubmitting(false);}
  }

  if (user) return <Navigate to={isReviewer(user) ? '/' : '/claims'} replace />;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const signedInUser = dev?.enabled ? await developerLogin(challenge.challenge_id,otp) : await login(email, password);
      const requested = location.state?.from;
      navigate(requested || (isReviewer(signedInUser) ? '/' : '/claims'), { replace: true });
    } catch (failure) {
      setError(failure.response?.data?.detail || 'Sign-in failed. Check your company email and password.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-shell">
      <div className="login-card glass-card">
        <img className="login-logo" src="/auditai-logo.png" alt="AuditAI mascot" />
        <p className="login-eyebrow">AUDITAI · {dev?.enabled ? 'LOCAL DEVELOPER MODE' : 'SECURE WORKSPACE'}</p>
        <h1>Sign in to your audit workspace</h1>
        <p className="login-subtitle">Use your provisioned company account. Your access to claims and review actions follows your assigned roles.</p>
        <form onSubmit={handleSubmit} className="login-form">
          {dev===null ? <p role="status">Checking sign-in options…</p> : dev.enabled ? <>
            <label htmlFor="developer-account">Demo account</label>
            <select id="developer-account" className="input" required value={email} disabled={submitting} onChange={e=>{setEmail(e.target.value);setChallenge(null);setOtp('');}}>
              <option value="">Choose an account</option>
              {dev.accounts.map(account=><option key={account.email} value={account.email}>{account.name} — {account.roles.join(', ')} ({account.email})</option>)}
            </select>
            <button className="btn btn-secondary" type="button" disabled={submitting||!email} onClick={generateOtp}>{submitting&&!challenge?'Generating…':'Generate developer OTP'}</button>
            {challenge && <>
              <p role="status">Your developer OTP: <strong style={{fontSize:'1.5rem',letterSpacing:'.2em'}}>{challenge.otp}</strong><br/>Valid for 2 minutes and one sign-in. A new code replaces the previous one.</p>
              <label htmlFor="developer-otp">Developer OTP</label><input id="developer-otp" className="input" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" required value={otp} onChange={e=>setOtp(e.target.value.replace(/\D/g,''))}/>
            </>}
          </> : <>
          <label htmlFor="login-email">Company email</label>
          <div className="login-input-wrap"><Mail size={18} /><input id="login-email" className="input" type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} required placeholder="name@company.com" /></div>
          <label htmlFor="login-password">Password</label>
          <div className="login-input-wrap"><LockKeyhole size={18} /><input id="login-password" className="input" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required placeholder="Enter your password" /></div>
          </>}
          {error && <p className="login-error" role="alert">{error}</p>}
          <button className="btn btn-primary login-submit" type="submit" disabled={submitting||dev===null||(dev.enabled&&(!challenge||otp.length!==6))}>{submitting ? 'Working…' : 'Sign in'}</button>
        </form>
        <p className="login-help">{dev?.enabled ? 'OTP is displayed on this page for local development only. Your selected account keeps its existing permissions.' : 'Need access? Ask your company administrator to provision your employee ID and role.'}</p>
      </div>
    </main>
  );
}
