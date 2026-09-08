import sys
sys.stdout.reconfigure(encoding='utf-8')
from src.core.parser import RobustAgentParser
from src.core.schema import SentimentAnalysisResult

bad_json = '{"stance": "bullish", "sentiment_score": 99.0, "is_sarcasm": false, "reasoning": "主力拉升"}'
res, feedback = RobustAgentParser.parse_or_build_feedback(bad_json, SentimentAnalysisResult)
print(f"解析是否成功: {res is not None}")
print("自愈反馈消息:\n" + str(feedback))
