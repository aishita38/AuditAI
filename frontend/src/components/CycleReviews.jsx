import React from 'react';
import { Link } from 'react-router-dom';
export default function CycleReviews() {
  return <section className="glass-card mt-6"><h2 className="text-xl font-semibold mb-4">Review in the shared queue</h2><p>Maker recommendations, checker decisions and comments for all case types are handled in one queue.</p><Link className="btn btn-secondary" to="/review-queue?case_type=circular_payment">Open shared review queue</Link></section>;
}
