# Benchmark Results

- Timestamp: 2026-04-23_13-30-38
- Cases: 15
- Verdict accuracy: 26.7%
- Bug recall: 27.3%
- False positive rate (per clean case): 0.60
- Avg latency: 95.5s
- Avg iterations: 0.60
- Error cases: 7

| case | verdict | bugs matched | findings | FP | latency (s) | iterations |
|------|---------|--------------|----------|----|-------------|------------|
| 01_validated_divide | MISS (test_error) | - | 1 | 1 | 110 | 2 |
| 02_safe_read_json | OK (None) | - | 1 | 1 | 66 | 1 |
| 03_validated_discount | MISS (source_bug) | - | 1 | 1 | 70 | 1 |
| 04_guarded_factorial | MISS (None) | - | 0 | 0 | 120 | 0 |
| 05_validated_user_api | MISS (None) | - | 0 | 0 | 120 | 0 |
| 06_divide_crash | MISS (None) | 1/1 | 1 | - | 66 | 1 |
| 07_dict_key_crash | MISS (None) | 0/1 | 0 | - | 120 | 0 |
| 08_list_index_crash | OK (source_bug) | 1/1 | 2 | - | 111 | 1 |
| 09_file_read_crash | MISS (None) | 0/1 | 1 | - | 71 | 1 |
| 10_parse_int_crash | OK (source_bug) | 0/1 | 1 | - | 45 | 1 |
| 11_process_order | MISS (None) | 0/2 | 0 | - | 120 | 0 |
| 12_cart_negative_qty | MISS (None) | 0/1 | 0 | - | 120 | 0 |
| 13_apply_discount_over | OK (source_bug) | 1/1 | 1 | - | 52 | 1 |
| 14_inventory_negative | MISS (None) | 0/1 | 0 | - | 120 | 0 |
| 15_transfer_negative_amount | MISS (None) | 0/1 | 0 | - | 120 | 0 |