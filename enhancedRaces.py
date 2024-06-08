data = """
14:32	PUNCHESTOWN	1/5 1-2-3-4
16:52	PUNCHESTOWN	1/5 1-2-3-4-5
14:05	BEVERLEY	1/5 1-2-3-4
17:00	BEVERLEY	1/5 1-2-3-4
14:20	NAVAN	1/5 1-2-3
14:55	NAVAN	1/5 1-2-3-4-5
16:05	NAVAN	1/5 1-2-3
15:00	HAYDOCK	1/5 1-2-3-4
16:10	HAYDOCK	1/5 1-2-3-4
16:45	HAYDOCK	1/5 1-2-3-4
15:20	CATTERICK	1/5 1-2-3-4
15:55	CATTERICK	1/5 1-2-3-4
17:25	CHEPSTOW	1/5 1-2-3
17:45	LINGFIELD	1/5 1-2-3
20:15	LINGFIELD	1/5 1-2-3-4-5
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