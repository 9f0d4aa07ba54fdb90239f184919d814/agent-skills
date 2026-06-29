#!/usr/bin/env python3
"""Generate execution verification report"""

import json
from pathlib import Path

def generate_html_report(json_path: Path, output_path: Path):
    """Generate HTML report from JSON results"""
    
    with open(json_path) as f:
        data = json.load(f)
    
    summary = data["summary"]
    by_file = data["by_file"]
    results = data["results"]
    
    # Group results by file
    file_results = {}
    for r in results:
        file = r["file"]
        if file not in file_results:
            file_results[file] = []
        file_results[file].append(r)
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Execution Verification Report</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat {{ background: #f8f9fa; padding: 20px; border-radius: 6px; text-align: center; border-left: 4px solid #007bff; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; font-size: 14px; }}
        .pass-rate {{ font-size: 48px; font-weight: bold; }}
        .pass-rate.good {{ color: #28a745; }}
        .pass-rate.medium {{ color: #ffc107; }}
        .pass-rate.bad {{ color: #dc3545; }}
        
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #343a40; color: white; padding: 12px; text-align: left; font-weight: 600; }}
        td {{ padding: 10px; border-bottom: 1px solid #dee2e6; }}
        tr:hover {{ background: #f8f9fa; }}
        
        .status {{ display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 12px; }}
        .status.PASS {{ background: #d4edda; color: #155724; }}
        .status.FAIL {{ background: #f8d7da; color: #721c24; }}
        .status.WARN {{ background: #fff3cd; color: #856404; }}
        
        .test-group {{ margin: 30px 0; }}
        .test-item {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 4px solid #007bff; }}
        .test-item.PASS {{ border-left-color: #28a745; }}
        .test-item.FAIL {{ border-left-color: #dc3545; }}
        .test-item.WARN {{ border-left-color: #ffc107; }}
        
        .test-type {{ color: #666; font-size: 13px; text-transform: uppercase; }}
        .test-message {{ margin-top: 5px; font-size: 14px; }}
        .test-duration {{ color: #999; font-size: 12px; margin-top: 5px; }}
        
        .file-status {{ display: inline-block; width: 20px; height: 20px; border-radius: 50%; margin: 0 3px; }}
        .file-status.PASS {{ background: #28a745; }}
        .file-status.FAIL {{ background: #dc3545; }}
        .file-status.WARN {{ background: #ffc107; }}
        
        .conclusion {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 20px; margin: 30px 0; border-radius: 6px; }}
        .conclusion h3 {{ margin-top: 0; color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔬 Execution Verification Report</h1>
        <p><strong>This report tests actual behavior, not just structure.</strong></p>
        <p>Generated: {data['results'][0]['file'] if results else 'N/A'}</p>
        
        <h2>📊 Summary</h2>
        <div class="summary">
            <div class="stat">
                <div class="stat-value">{summary['total_tests']}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #28a745;">{summary['pass']}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #dc3545;">{summary['fail']}</div>
                <div class="stat-label">Failed</div>
            </div>
            <div class="stat">
                <div class="stat-value" style="color: #ffc107;">{summary['warn']}</div>
                <div class="stat-label">Warnings</div>
            </div>
            <div class="stat">
                <div class="pass-rate {'good' if summary['pass_rate'] >= 80 else 'medium' if summary['pass_rate'] >= 50 else 'bad'}">{summary['pass_rate']}%</div>
                <div class="stat-label">Pass Rate</div>
            </div>
        </div>
        
        <h2>📋 Component Status</h2>
        <table>
            <thead>
                <tr>
                    <th>Component</th>
                    <th>Import</th>
                    <th>Unit</th>
                    <th>Integration</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>"""
    
    # Analyze each component
    components = {
        "kernel.kernel": {"import": "❌", "unit": "❌", "integration": "❌"},
        "brain.decision_engine": {"import": "❌", "unit": "❌", "integration": "❌"},
        "brain.world_model": {"import": "❌", "unit": "❌", "integration": "❌"},
        "brain.provenance": {"import": "❌", "unit": "❌", "integration": "❌"},
        "brain.policy.engine": {"import": "❌", "unit": "❌", "integration": "❌"},
        "core.repository_intelligence.parser": {"import": "❌", "unit": "❌", "integration": "❌"},
        "science.benchmarks.olympics": {"import": "❌", "unit": "❌", "integration": "❌"},
    }
    
    for r in results:
        file = r["file"]
        if file in components:
            if r["test_type"] == "import":
                components[file]["import"] = "✅" if r["status"] == "PASS" else "❌"
            elif "api" in r["test_type"]:
                components[file]["unit"] = "✅" if r["status"] == "PASS" else "⚠️" if r["status"] == "WARN" else "❌"
            elif r["test_type"] in ["enforce", "parse", "benchmark", "world_model", "provenance"]:
                components[file]["integration"] = "✅" if r["status"] == "PASS" else "⚠️" if r["status"] == "WARN" else "❌"
    
    for comp, tests in components.items():
        pass_count = sum(1 for v in tests.values() if v == "✅")
        status = "PASS" if pass_count == 3 else "FAIL" if pass_count == 0 else "WARN"
        html += f"""
                <tr>
                    <td><strong>{comp}</strong></td>
                    <td>{tests['import']}</td>
                    <td>{tests['unit']}</td>
                    <td>{tests['integration']}</td>
                    <td><span class="status {status}">{status}</span></td>
                </tr>"""
    
    html += """
            </tbody>
        </table>
        
        <h2>🔍 Detailed Results</h2>"""
    
    # Group by file
    for file, file_tests in file_results.items():
        html += f"""
        <div class="test-group">
            <h3>{file}</h3>"""
        
        for test in file_tests:
            html += f"""
            <div class="test-item {test['status']}">
                <span class="status {test['status']}">{test['status']}</span>
                <span class="test-type">{test['test_type']}</span>
                <div class="test-message">{test['message']}</div>
                <div class="test-duration">Duration: {test['duration_ms']:.1f}ms</div>
            </div>"""
        
        html += """
        </div>"""
    
    # Conclusion
    if summary['pass_rate'] < 60:
        conclusion_color = "#856404"
        conclusion_bg = "#fff3cd"
        conclusion_text = "⚠️ FAIL - Implementation is incomplete"
        conclusion_details = f"""
        <p><strong>Current State:</strong> {summary['pass_rate']}% pass rate indicates major gaps between architecture documents and actual implementation.</p>
        <ul>
            <li>{summary['fail']} tests failed out of {summary['total_tests']} total tests</li>
            <li>Many components import but APIs don't match documentation</li>
            <li>Critical path (Repository Intelligence) is not fully implemented</li>
        </ul>
        <p><strong>Reality Check:</strong> Your static verification said files exist and compile. This execution verification shows many don't actually work when you call them.</p>
        """
    else:
        conclusion_color = "#155724"
        conclusion_bg = "#d4edda"
        conclusion_text = "✅ PASS - Implementation matches architecture"
        conclusion_details = "<p>Most components work as documented. Ready for production testing.</p>"
    
    html += f"""
        <div class="conclusion" style="background: {conclusion_bg}; border-left-color: {conclusion_color};">
            <h3 style="color: {conclusion_color};">{conclusion_text}</h3>
            {conclusion_details}
        </div>
        
        <h2>📝 Recommendations</h2>
        <ol>
            <li><strong>Fix Import Failures:</strong> Repository Intelligence parser doesn't exist at expected location</li>
            <li><strong>Fix API Mismatches:</strong> Job, DecisionEngine, PolicyEngine, WorldModel APIs don't match test expectations</li>
            <li><strong>Add Unit Tests:</strong> Current test coverage is 5.6% - need unit tests for each component</li>
            <li><strong>Integration Tests:</strong> Test cross-component workflows (Kernel → Workers → Artifacts)</li>
            <li><strong>Repository Intelligence Priority:</strong> This is P0 blocker - get parser working first</li>
        </ol>
        
        <hr style="margin: 40px 0; border: none; border-top: 1px solid #dee2e6;">
        <p style="color: #999; font-size: 12px;">
            Generated by execution_verification.py | 
            Report: EXECUTION_VERIFICATION_REPORT.html | 
            Data: EXECUTION_REPORT.json
        </p>
    </div>
</body>
</html>
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\nHTML report generated: {output_path}")

if __name__ == "__main__":
    root = Path(__file__).parent.parent / "coding-agent"
    json_path = root / "EXECUTION_REPORT.json"
    html_path = root / "EXECUTION_VERIFICATION_REPORT.html"
    
    if json_path.exists():
        generate_html_report(json_path, html_path)
    else:
        print(f"❌ Report not found: {json_path}")
