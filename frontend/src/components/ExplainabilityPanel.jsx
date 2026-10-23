import React from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import { useNavigate } from 'react-router-dom';

const REASON_COLORS = ['#ee895f', '#a28bf0', '#efbd58', '#94bf95', '#7e91ee', '#e9785b', '#d8a2ff', '#7ed1c3'];

function formatAmount(value) {
  return `₹${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function DetectionTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="glass-card" style={{ padding: '12px 14px', minWidth: 205 }}>
      <div className="font-semibold text-accent-primary mb-1">{point.claim_id}</div>
      <div className="text-sm">{point.employee_name} · {point.vendor_name}</div>
      <div className="text-sm mt-2">Score: <strong>{point.score.toFixed(1)} / 100</strong></div>
      <div className="text-sm">Amount: <strong>{formatAmount(point.amount)}</strong></div>
      <div className="text-xs text-secondary mt-2">Main signal: {point.reasonDetail}</div>
      <div className="text-xs text-muted mt-1">Click to open claim evidence</div>
    </div>
  );
}

function ReasonTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const reason = payload[0].payload;
  return (
    <div className="glass-card" style={{ padding: '12px 14px' }}>
      <div className="font-semibold">{reason.label}</div>
      <div className="text-sm text-secondary mt-1">Largest contribution in {reason.flagged_claims} flagged claim{reason.flagged_claims === 1 ? '' : 's'}</div>
      <div className="text-xs text-muted mt-1">Mean absolute contribution: {reason.mean_impact.toFixed(4)}</div>
    </div>
  );
}

export default function ExplainabilityPanel({ claims = [], reasonBreakdown = [], threshold = 50 }) {
  const navigate = useNavigate();
  const points = claims
    .filter(claim => claim.fraud_score !== null && claim.fraud_score !== undefined)
    .map((claim, index) => ({
      claim_id: claim.claim_id,
      employee_name: claim.employee_name,
      vendor_name: claim.vendor_name,
      amount: Number(claim.claimed_amount || 0),
      score: Number(claim.fraud_score || 0) * 100,
      size: Math.max(70, Number(claim.fraud_score || 0) * 180),
      reason: claim.dominant_reason || 'Model score only',
      reasonDetail: claim.dominant_reason_detail || claim.dominant_reason || 'Model score only',
      color: REASON_COLORS[index % REASON_COLORS.length],
    }));

  return (
    <div className="grid-cols-2 mb-6" style={{ alignItems: 'stretch' }}>
      <div className="glass-card">
        <div className="flex justify-between items-start gap-4 mb-2">
          <div>
            <h3 className="text-lg font-semibold">Flagged claims detection map</h3>
            <p className="text-xs text-secondary mt-1">Each point is a flagged entry. Higher scores carry stronger anomaly evidence.</p>
          </div>
          <span className="badge badge-orange text-xs">Evidence map</span>
        </div>
        {points.length === 0 ? (
          <p className="text-secondary text-center py-12">No flagged claims with model scores yet.</p>
        ) : (
          <div style={{ height: 320, width: '100%' }}>
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 20, right: 18, bottom: 18, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="amount"
                  name="Claim amount"
                  tickFormatter={value => `₹${Math.round(value / 1000)}k`}
                  tick={{ fontSize: 11 }}
                />
                <YAxis
                  type="number"
                  dataKey="score"
                  name="Anomaly score"
                  domain={[0, 100]}
                  tick={{ fontSize: 11 }}
                />
                <ZAxis type="number" dataKey="size" range={[65, 260]} />
                {threshold != null && <ReferenceLine y={threshold} stroke="var(--accent-primary)" strokeDasharray="5 5" label={{ value: 'Review threshold', fill: 'var(--text-secondary)', fontSize: 11 }} />}
                <Tooltip content={<DetectionTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                <Scatter
                  name="Flagged claims"
                  data={points}
                  onClick={point => point?.claim_id && navigate(`/claims/${point.claim_id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  {points.map(point => <Cell key={point.claim_id} fill={point.color} />)}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="flex justify-between text-xs text-muted mt-1">
          <span>X: claimed amount</span>
          <span>Y: anomaly index (0–100)</span>
        </div>
      </div>

      <div className="glass-card">
        <div className="mb-2">
          <h3 className="text-lg font-semibold">Why claims were flagged</h3>
          <p className="text-xs text-secondary mt-1">Largest model contributions aggregated across the scored queue.</p>
        </div>
        {reasonBreakdown.length === 0 ? (
          <p className="text-secondary text-center py-12">Explanation evidence will appear after scoring.</p>
        ) : (
          <div style={{ height: 320, width: '100%' }}>
            <ResponsiveContainer>
              <BarChart
                layout="vertical"
                data={reasonBreakdown}
                margin={{ top: 8, right: 18, bottom: 8, left: 105 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" allowDecimals={false} />
                <YAxis type="category" dataKey="label" width={110} tick={{ fontSize: 11 }} />
                <Tooltip content={<ReasonTooltip />} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
                <Bar dataKey="flagged_claims" name="Flagged claims" radius={[0, 5, 5, 0]}>
                  {reasonBreakdown.map((reason, index) => <Cell key={reason.feature} fill={REASON_COLORS[index % REASON_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="text-xs text-muted mt-1">Bars show contribution magnitude; claim detail shows whether each signal increased or reduced anomaly evidence.</div>
      </div>
    </div>
  );
}
