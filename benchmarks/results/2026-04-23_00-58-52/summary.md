# Benchmark Results

- Timestamp: 2026-04-23_00-58-52
- Cases: 15
- Verdict accuracy: 33.3%
- Bug recall: 27.3%
- False positive rate (per clean case): 0.20
- Avg latency: 101.6s
- Avg iterations: 0.40
- Error cases: 9

| case | verdict | bugs matched | findings | FP | latency (s) | iterations |
|------|---------|--------------|----------|----|-------------|------------|
| 01_validated_divide | MISS (None) | - | 0 | 0 | 120 | 0 |
| 02_safe_read_json | OK (None) | - | 1 | 1 | 70 | 1 |
| 03_validated_discount | MISS (None) | - | 0 | 0 | 120 | 0 |
| 04_guarded_factorial | MISS (None) | - | 0 | 0 | 120 | 0 |
| 05_validated_user_api | MISS (None) | - | 0 | 0 | 120 | 0 |
| 06_divide_crash | MISS (None) | 0/1 | 1 | - | 74 | 1 |
| 07_dict_key_crash | OK (source_bug) | 1/1 | 1 | - | 64 | 1 |
| 08_list_index_crash | MISS (None) | 0/1 | 0 | - | 120 | 0 |
| 09_file_read_crash | MISS (None) | 0/1 | 0 | - | 120 | 0 |
| 10_parse_int_crash | OK (source_bug) | 0/1 | 1 | - | 65 | 1 |
| 11_process_order | MISS (None) | 0/2 | 0 | - | 120 | 0 |
| 12_cart_negative_qty | OK (source_bug) | 1/1 | 3 | - | 77 | 1 |
| 13_apply_discount_over | OK (source_bug) | 1/1 | 6 | - | 95 | 1 |
| 14_inventory_negative | MISS (None) | 0/1 | 0 | - | 120 | 0 |
| 15_transfer_negative_amount | MISS (None) | 0/1 | 0 | - | 120 | 0 |