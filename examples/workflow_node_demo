def _mock_parser_response(self) -> str:
    return json.dumps({
        "format_type": "standard_script",
        "scenes": [
            {
                "scene_id": "s1",
                "description": "林然坐在客厅沙发上，手中拿着咖啡杯",
                "characters": ["林然"],
                "location": "客厅"
            }
        ],
        "characters": [
            {
                "name": "林然",
                "description": "年轻男性，穿着休闲服装"
            }
        ],
        "dialogues": [
            {
                "speaker": "林然",
                "content": "你好吗？",
                "emotional_tone": "neutral"
            }
        ]
    }, ensure_ascii=False)

def _mock_planner_response(self) -> str:
    return json.dumps({
        "timeline_segments": [
            {
                "segment_id": "s001",
                "time_range": [0.0, 5.0],
                "duration": 5.0,
                "content": "林然坐在沙发上，拿着咖啡杯",
                "characters": ["林然"],
                "estimated_duration": 5.0
            }
        ],
        "pacing_analysis": "normal",
        "total_duration": 5.0
    }, ensure_ascii=False)

def _mock_continuity_response(self) -> str:
    return json.dumps({
        "anchored_segments": [
            {
                "segment_id": "s001",
                "start_constraint": "林然坐在沙发左侧，手持咖啡杯",
                "end_constraint": "林然保持坐姿，咖啡杯在手中",
                "continuity_hooks": ["coffee_cup_position", "sitting_posture"]
            }
        ],
        "continuity_rules": [
            "咖啡杯必须始终在画面中",
            "林然的服装保持一致"
        ]
    }, ensure_ascii=False)

def _mock_visual_response(self) -> str:
    return json.dumps({
        "shots": [
            {
                "shot_id": "s001_shot1",
                "time_range": [0.0, 5.0],
                "prompt": "A young man (Lin Ran) sitting on a modern gray sofa, holding a white ceramic coffee cup in his right hand. Soft natural lighting from window, cinematic shallow depth of field, warm color grading. Medium close-up shot, slow subtle push-in.",
                "camera": "medium_close_up",
                "movement": "slow_push_in"
            }
        ],
        "style_guide": "cinematic natural lighting"
    }, ensure_ascii=False)

def _mock_reviewer_response(self) -> str:
    return json.dumps({
        "decision": "approved",
        "score": 0.85,
        "issues": [],
        "suggestions": ["可以考虑添加更多镜头变化"],
        "can_proceed": True
    }, ensure_ascii=False)
