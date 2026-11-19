"""UI Styles and Custom CSS for DataFix Streamlit Frontend."""

CUSTOM_CSS = """
<style>
/* Main Header and Brand */
.main-header {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    padding: 1.8rem 2rem;
    border-radius: 12px;
    color: white;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}
.main-header h1 {
    color: white !important;
    margin: 0;
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: -0.5px;
}
.main-header p {
    color: #e0e7ff;
    margin: 0.5rem 0 0 0;
    font-size: 1.05rem;
}

/* Metric Cards */
.metric-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 1.2rem;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    margin-bottom: 1rem;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.metric-label {
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748b;
    margin-bottom: 0.25rem;
}
.metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1e293b;
}
.metric-sub {
    font-size: 0.85rem;
    color: #64748b;
    margin-top: 0.25rem;
}

/* Recommendation Cards */
.rec-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 5px solid #3b82f6;
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03);
}
.rec-card-destructive {
    border-left-color: #ef4444;
}
.rec-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 0.4rem;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 9999px;
    margin-right: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-safe {
    background-color: #ecfdf5;
    color: #065f46;
    border: 1px solid #a7f3d0;
}
.badge-destructive {
    background-color: #fef2f2;
    color: #991b1b;
    border: 1px solid #fecaca;
}
.badge-critical {
    background-color: #fee2e2;
    color: #991b1b;
}
.badge-high {
    background-color: #ffedd5;
    color: #9a3412;
}
.badge-medium {
    background-color: #fef9c3;
    color: #854d0e;
}
.badge-low {
    background-color: #e0f2fe;
    color: #075985;
}

/* Quality Score Rating Pills */
.rating-pill {
    display: inline-block;
    padding: 0.35rem 0.85rem;
    border-radius: 20px;
    font-weight: 700;
    font-size: 0.95rem;
}
.rating-excellent {
    background-color: #d1fae5;
    color: #065f46;
}
.rating-good {
    background-color: #e0f2fe;
    color: #0369a1;
}
.rating-fair {
    background-color: #fef3c7;
    color: #92400e;
}
.rating-poor {
    background-color: #fee2e2;
    color: #991b1b;
}
</style>
"""
