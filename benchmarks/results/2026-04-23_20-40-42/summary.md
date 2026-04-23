# Benchmark Results

- Timestamp: 2026-04-23_20-40-42
- Cases: 15
- Verdict accuracy: 40.0%
- Bug recall: 18.2%
- False positive rate (per clean case): 0.60
- Avg latency: 129.0s
- Avg iterations: 0.67
- Error cases: 6

| case | verdict | bugs matched | findings | FP | latency (s) | iterations |
|------|---------|--------------|----------|----|-------------|------------|
| 01_validated_divide | OK (None) | - | 1 | 1 | 65 | 1 |
| 02_safe_read_json | OK (None) | - | 1 | 1 | 78 | 1 |
| 03_validated_discount | OK (None) | - | 1 | 1 | 124 | 1 |
| 04_guarded_factorial | MISS (None) | - | 0 | 0 | 180 | 0 |
| 05_validated_user_api | MISS (None) | - | 0 | 0 | 180 | 0 |
| 06_divide_crash | MISS (None) | 0/1 | 1 | - | 88 | 1 |
| 07_dict_key_crash | MISS (test_error) | 0/1 | 1 | - | 170 | 2 |
| 08_list_index_crash | MISS (None) | 0/1 | 0 | - | 180 | 0 |
| 09_file_read_crash | MISS (None) | 0/1 | 1 | - | 127 | 1 |
| 10_parse_int_crash | OK (source_bug) | 0/1 | 1 | - | 61 | 1 |
| 11_process_order | MISS (None) | 0/2 | 0 | - | 180 | 0 |
| 12_cart_negative_qty | OK (source_bug) | 1/1 | 3 | - | 81 | 1 |
| 13_apply_discount_over | OK (source_bug) | 1/1 | 1 | - | 61 | 1 |
| 14_inventory_negative | MISS (None) | 0/1 | 0 | - | 180 | 0 |
| 15_transfer_negative_amount | MISS (None) | 0/1 | 0 | - | 180 | 0 |