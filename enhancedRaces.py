data = """
14:00	NEWBURY	1/5 1-2-3-4
14:30	NEWBURY	1/5 1-2-3-4
17:10	NEWBURY	1/5 1-2-3-4
17:40	NEWBURY	1/5 1-2-3-4
14:15	YORK	1/5 1-2-3-4
14:45	YORK	1/5 1-2-3-4-5
16:45	YORK	1/5 1-2-3-4-5
17:20	YORK	1/5 1-2-3-4-5
16:55	NEWMARKET	1/5 1-2-3-4
17:25	LEOPARDSTOWN	1/5 1-2-3-4-5
17:55	LEOPARDSTOWN	1/5 1-2-3-4-5
18:30	LEOPARDSTOWN	1/5 1-2-3-4
19:40	LEOPARDSTOWN	1/5 1-2-3-4-5-6
20:15	LEOPARDSTOWN	1/5 1-2-3-4
17:00	KILBEGGAN	1/5 1-2-3-4
19:55	KILBEGGAN	1/5 1-2-3-4
18:40	HAMILTON	1/5 1-2-3
18:55	AINTREE	1/5 1-2-3-4
20:05	AINTREE	1/5 1-2-3-4
"""

lines = data.strip().split('\n')
lines.sort(key=lambda line: line.split(' ')[0])
sorted_data = '\n'.join(lines)

print(sorted_data)
# odds = [17.0, 12.0, 23.0, 17.0, 17.0, 15.0, 8.5, 4.0, 17.0, 8.0, 10.0, 21.0, 9.0, 15.0, 21.0, 11.0, 9.0, 26.0, 26.0, 41.0, 41.0, 17.0, 17.0, 19.0, 15.0, 41.0]
# split_index = int(len(odds) * 0.7)
# early_odds = odds[:split_index]
# late_odds = odds[split_index:]

# early_avg = sum(early_odds) / len(early_odds)
# late_avg = sum(late_odds) / len(late_odds)

# print(f"Early average: {early_avg}")
# print(f"Late average: {late_avg}")

# if late_avg > early_avg:
#     print("The average of the last 30% of odds is higher than the first 70%.")
# else:
#     print("The average of the last 30% of odds is not higher than the first 70%.")