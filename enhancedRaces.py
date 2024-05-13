data = """
14:45	KILLARNEY	1/5 1-2-3-4
16:30	KILLARNEY	1/5 1-2-3-4
16:45	LEOPARDSTOWN	1/5 1-2-3-4
14:53	LUDLOW	1/5 1-2-3
17:13	LUDLOW	1/5 1-2-3-4
15:50	PLUMPTON	1/5 1-2-3-4
17:27	NEWCASTLE	1/5 1-2-3
18:00	NEWCASTLE	1/5 1-2-3-4
19:00	NEWCASTLE	1/5 1-2-3-4
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