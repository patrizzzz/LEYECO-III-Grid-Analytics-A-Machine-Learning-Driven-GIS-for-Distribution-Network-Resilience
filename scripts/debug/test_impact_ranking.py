import sys
import os

# Add the current directory to sys.path to import app and models
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app import app
from extensions import db
from models import DistributionTransformer, Customer, SecondaryServiceDrop
from analysis_services import get_grid_health_analytics

def test_impact_ranking():
    output_file = "test_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        with app.app_context():
            f.write("Testing Customer Impact Ranking Logic...\n")
            
            # 1. Fetch grid health analytics
            results = get_grid_health_analytics()
            
            if not results or 'details' not in results:
                f.write("Error: No details found in results.\n")
                return

            details = results['details']
            summary = results['summary']
            
            f.write(f"Total Transformers Analyzed: {summary['total']}\n")
            f.write(f"Critical: {summary['critical']}, High: {summary['high']}, Medium: {summary['medium']}, Low: {summary['low']}\n")
            
            if not details:
                f.write("No transformer details to verify.\n")
                return

            # 2. Verify Ranking
            impact_scores = [d['impact_score'] for d in details]
            is_sorted = all(impact_scores[i] >= impact_scores[i+1] for i in range(len(impact_scores)-1))
            f.write(f"Are transformers sorted by impact_score? {'Yes' if is_sorted else 'No'}\n")
            
            # 3. Verify Fields
            if details:
                sample = details[0]
                required_fields = ['impact_rank', 'impact_score', 'criticality_score', 'customer_count', 'utilization_percent', 'risk_score', 'risk_level']
                missing = [f_field for f_field in required_fields if f_field not in sample]
                
                if missing:
                    f.write(f"Error: Missing fields in output: {missing}\n")
                else:
                    f.write(f"Sample Top Transformer (#{sample['impact_rank']}):\n")
                    f.write(f"  ID: {sample['transformer_id']}\n")
                    f.write(f"  Impact Score: {sample['impact_score']}\n")
                    f.write(f"  Criticality Score: {sample['criticality_score']}\n")
                    f.write(f"  Customers Served: {sample['customer_count']}\n")
                    f.write(f"  Utilization: {sample['utilization_percent']}%\n")
                    f.write(f"  ML Risk Score: {sample['risk_score']}%\n")
                    f.write(f"  Risk Level: {sample['risk_level']}\n")

                # 4. Verify Logic (Mental check against sample)
                # impact_score = (risk_score / 100) * criticality
                expected_impact = round((sample['risk_score'] / 100.0) * sample['criticality_score'], 2)
                if abs(sample['impact_score'] - expected_impact) < 0.1:
                    f.write("✓ Impact score calculation matches formula.\n")
                else:
                    f.write(f"✗ Impact score mismatch! Expected: {expected_impact}, Actual: {sample['impact_score']}\n")

if __name__ == "__main__":
    test_impact_ranking()
