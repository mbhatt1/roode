"""
Generate performance benchmark reports.

Consolidates benchmark results and generates reports in various formats.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


class BenchmarkReport:
    """Generate performance benchmark reports."""
    
    def __init__(self, output_dir: str = ".benchmarks"):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results: Dict[str, Any] = {}
        self.timestamp = datetime.now().isoformat()
    
    def add_benchmark_results(self, name: str, results: Dict[str, Any]) -> None:
        """
        Add benchmark results to report.
        
        Args:
            name: Benchmark name
            results: Benchmark results dictionary
        """
        self.results[name] = results
    
    def generate_json_report(self, filename: str = "benchmark_results.json") -> str:
        """
        Generate JSON report.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to generated report
        """
        output_path = self.output_dir / filename
        
        report = {
            "timestamp": self.timestamp,
            "benchmarks": self.results,
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        return str(output_path)
    
    def generate_markdown_report(self, filename: str = "BENCHMARK_REPORT.md") -> str:
        """
        Generate Markdown report.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to generated report
        """
        output_path = self.output_dir / filename
        
        lines = [
            "# Performance Benchmark Report",
            "",
            f"Generated: {self.timestamp}",
            "",
            "## Summary",
            "",
        ]
        
        # Add summary table
        lines.append("| Benchmark | Iterations | Mean Time | Median Time | P95 Time |")
        lines.append("|-----------|------------|-----------|-------------|----------|")
        
        for category_name, category_results in sorted(self.results.items()):
            for bench_name, bench_data in sorted(category_results.items()):
                if isinstance(bench_data, dict) and "mean" in bench_data:
                    lines.append(
                        f"| {category_name}/{bench_name} | "
                        f"{bench_data.get('iterations', 'N/A')} | "
                        f"{bench_data['mean']*1000:.3f} ms | "
                        f"{bench_data.get('median', 0)*1000:.3f} ms | "
                        f"{bench_data.get('p95', 0)*1000:.3f} ms |"
                    )
        
        lines.append("")
        lines.append("## Detailed Results")
        lines.append("")
        
        # Add detailed sections
        for category_name, category_results in sorted(self.results.items()):
            lines.append(f"### {category_name}")
            lines.append("")
            
            for bench_name, bench_data in sorted(category_results.items()):
                if isinstance(bench_data, dict) and "mean" in bench_data:
                    lines.append(f"#### {bench_name}")
                    lines.append("")
                    lines.append(f"- **Iterations**: {bench_data.get('iterations', 'N/A')}")
                    lines.append(f"- **Total Time**: {bench_data.get('total_time', 0):.3f}s")
                    lines.append(f"- **Mean**: {bench_data['mean']*1000:.3f} ms")
                    lines.append(f"- **Median**: {bench_data.get('median', 0)*1000:.3f} ms")
                    lines.append(f"- **Min**: {bench_data.get('min', 0)*1000:.3f} ms")
                    lines.append(f"- **Max**: {bench_data.get('max', 0)*1000:.3f} ms")
                    lines.append(f"- **P95**: {bench_data.get('p95', 0)*1000:.3f} ms")
                    lines.append(f"- **P99**: {bench_data.get('p99', 0)*1000:.3f} ms")
                    lines.append("")
        
        with open(output_path, 'w') as f:
            f.write("\n".join(lines))
        
        return str(output_path)
    
    def generate_html_report(self, filename: str = "benchmark_report.html") -> str:
        """
        Generate HTML report with charts.
        
        Args:
            filename: Output filename
            
        Returns:
            Path to generated report
        """
        output_path = self.output_dir / filename
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Performance Benchmark Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #666;
            margin-top: 30px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: white;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .metric {{
            display: inline-block;
            margin: 10px;
            padding: 15px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #4CAF50;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .timestamp {{
            color: #999;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <h1>Performance Benchmark Report</h1>
    <p class="timestamp">Generated: {self.timestamp}</p>
    
    <h2>Summary</h2>
    <table>
        <thead>
            <tr>
                <th>Benchmark</th>
                <th>Iterations</th>
                <th>Mean Time</th>
                <th>Median Time</th>
                <th>P95 Time</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for category_name, category_results in sorted(self.results.items()):
            for bench_name, bench_data in sorted(category_results.items()):
                if isinstance(bench_data, dict) and "mean" in bench_data:
                    html += f"""
            <tr>
                <td>{category_name}/{bench_name}</td>
                <td>{bench_data.get('iterations', 'N/A')}</td>
                <td>{bench_data['mean']*1000:.3f} ms</td>
                <td>{bench_data.get('median', 0)*1000:.3f} ms</td>
                <td>{bench_data.get('p95', 0)*1000:.3f} ms</td>
            </tr>
"""
        
        html += """
        </tbody>
    </table>
    
    <h2>Detailed Results</h2>
"""
        
        for category_name, category_results in sorted(self.results.items()):
            html += f"""
    <h3>{category_name}</h3>
"""
            for bench_name, bench_data in sorted(category_results.items()):
                if isinstance(bench_data, dict) and "mean" in bench_data:
                    html += f"""
    <h4>{bench_name}</h4>
    <div>
        <div class="metric">
            <div class="metric-value">{bench_data.get('iterations', 'N/A')}</div>
            <div class="metric-label">Iterations</div>
        </div>
        <div class="metric">
            <div class="metric-value">{bench_data['mean']*1000:.2f} ms</div>
            <div class="metric-label">Mean Time</div>
        </div>
        <div class="metric">
            <div class="metric-value">{bench_data.get('median', 0)*1000:.2f} ms</div>
            <div class="metric-label">Median Time</div>
        </div>
        <div class="metric">
            <div class="metric-value">{bench_data.get('min', 0)*1000:.2f} ms</div>
            <div class="metric-label">Min Time</div>
        </div>
        <div class="metric">
            <div class="metric-value">{bench_data.get('max', 0)*1000:.2f} ms</div>
            <div class="metric-label">Max Time</div>
        </div>
        <div class="metric">
            <div class="metric-value">{bench_data.get('p95', 0)*1000:.2f} ms</div>
            <div class="metric-label">P95 Time</div>
        </div>
        <div class="metric">
            <div class="metric-value">{bench_data.get('p99', 0)*1000:.2f} ms</div>
            <div class="metric-label">P99 Time</div>
        </div>
    </div>
"""
        
        html += """
</body>
</html>
"""
        
        with open(output_path, 'w') as f:
            f.write(html)
        
        return str(output_path)
    
    def compare_with_baseline(self, baseline_path: str) -> Dict[str, Any]:
        """
        Compare current results with baseline.
        
        Args:
            baseline_path: Path to baseline JSON report
            
        Returns:
            Comparison results
        """
        with open(baseline_path, 'r') as f:
            baseline = json.load(f)
        
        comparisons = {}
        
        for category_name, category_results in self.results.items():
            if category_name not in baseline.get("benchmarks", {}):
                continue
            
            comparisons[category_name] = {}
            baseline_category = baseline["benchmarks"][category_name]
            
            for bench_name, bench_data in category_results.items():
                if bench_name not in baseline_category:
                    continue
                
                if not isinstance(bench_data, dict) or "mean" not in bench_data:
                    continue
                
                baseline_data = baseline_category[bench_name]
                if not isinstance(baseline_data, dict) or "mean" not in baseline_data:
                    continue
                
                current_mean = bench_data["mean"]
                baseline_mean = baseline_data["mean"]
                
                speedup = baseline_mean / current_mean if current_mean > 0 else 0
                improvement = (1 - current_mean / baseline_mean) * 100 if baseline_mean > 0 else 0
                
                comparisons[category_name][bench_name] = {
                    "baseline_mean": baseline_mean,
                    "current_mean": current_mean,
                    "speedup": speedup,
                    "improvement_percent": improvement,
                    "regression": improvement < -5.0,  # >5% slower is regression
                }
        
        return comparisons
    
    def generate_comparison_report(
        self,
        baseline_path: str,
        filename: str = "COMPARISON_REPORT.md"
    ) -> str:
        """
        Generate comparison report against baseline.
        
        Args:
            baseline_path: Path to baseline JSON report
            filename: Output filename
            
        Returns:
            Path to generated report
        """
        comparisons = self.compare_with_baseline(baseline_path)
        output_path = self.output_dir / filename
        
        lines = [
            "# Performance Comparison Report",
            "",
            f"Current: {self.timestamp}",
            f"Baseline: {baseline_path}",
            "",
            "## Summary",
            "",
        ]
        
        # Count improvements and regressions
        improvements = 0
        regressions = 0
        
        for category_results in comparisons.values():
            for comparison in category_results.values():
                if comparison["regression"]:
                    regressions += 1
                elif comparison["improvement_percent"] > 5.0:
                    improvements += 1
        
        lines.append(f"- **Improvements**: {improvements}")
        lines.append(f"- **Regressions**: {regressions}")
        lines.append("")
        lines.append("| Benchmark | Baseline | Current | Speedup | Change |")
        lines.append("|-----------|----------|---------|---------|--------|")
        
        for category_name, category_results in sorted(comparisons.items()):
            for bench_name, comparison in sorted(category_results.items()):
                status = "🔴" if comparison["regression"] else "🟢" if comparison["improvement_percent"] > 5.0 else "⚪"
                lines.append(
                    f"| {status} {category_name}/{bench_name} | "
                    f"{comparison['baseline_mean']*1000:.2f} ms | "
                    f"{comparison['current_mean']*1000:.2f} ms | "
                    f"{comparison['speedup']:.2f}x | "
                    f"{comparison['improvement_percent']:+.1f}% |"
                )
        
        lines.append("")
        
        with open(output_path, 'w') as f:
            f.write("\n".join(lines))
        
        return str(output_path)


def main():
    """Example usage of report generator."""
    # Create sample report
    report = BenchmarkReport()
    
    # Add sample data
    report.add_benchmark_results("file_operations", {
        "read_small_file": {
            "iterations": 100,
            "mean": 0.001,
            "median": 0.0009,
            "min": 0.0008,
            "max": 0.003,
            "p95": 0.0015,
            "p99": 0.002,
        }
    })
    
    # Generate reports
    json_path = report.generate_json_report()
    print(f"JSON report: {json_path}")
    
    md_path = report.generate_markdown_report()
    print(f"Markdown report: {md_path}")
    
    html_path = report.generate_html_report()
    print(f"HTML report: {html_path}")


if __name__ == "__main__":
    main()