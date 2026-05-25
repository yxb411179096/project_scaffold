OUTLINE_MAP = {
    "reading": [
        "cover",
        "objectives",
        "key_points",
        "difficult_points",
        "lead_in",
        "prediction",
        "fast_reading",
        "careful_reading",
        "vocabulary_support",
        "task_design",
        "classroom_interaction",
        "summary",
        "homework",
        "blackboard_design",
    ],
    "grammar": [
        "cover",
        "objectives",
        "key_points",
        "difficult_points",
        "lead_in",
        "grammar_discovery",
        "grammar_rule",
        "guided_practice",
        "controlled_practice",
        "task_design",
        "classroom_interaction",
        "summary",
        "homework",
        "blackboard_design",
    ],
    "writing": [
        "cover",
        "objectives",
        "key_points",
        "difficult_points",
        "lead_in",
        "writing_task_analysis",
        "useful_expressions",
        "writing_structure",
        "sample_appreciation",
        "guided_writing",
        "classroom_interaction",
        "summary",
        "homework",
        "blackboard_design",
    ],
    "listening_speaking": [
        "cover",
        "objectives",
        "key_points",
        "difficult_points",
        "lead_in",
        "pre_listening",
        "while_listening",
        "post_listening",
        "vocabulary_support",
        "speaking_task",
        "classroom_interaction",
        "summary",
        "homework",
        "blackboard_design",
    ],
    "revision": [
        "cover",
        "objectives",
        "key_points",
        "difficult_points",
        "lead_in",
        "knowledge_review",
        "vocabulary_support",
        "grammar_review",
        "integrated_task",
        "task_design",
        "classroom_interaction",
        "summary",
        "homework",
        "blackboard_design",
    ],
}

SLIDE_LIBRARY = {
    "cover": {
        "title": "{course_title}",
        "default_content": [
            "{unit}",
            "{lesson_type_display}",
            "{grade} | {textbook}",
        ],
        "refresh_content": [
            "{unit}",
            "{lesson_type_display}",
            "Focus: {theme_keyword}",
        ],
        "teacher_notes": "Open the lesson, greet the class, and introduce the focus of {course_title}.",
        "refresh_notes": "Start with a concise hook and show students the lesson focus on {theme_keyword}.",
        "teaching_purpose": "Set the lesson context and establish a clear learning theme.",
        "estimated_time": "2 minutes",
        "interaction_type": "Teacher introduction",
    },
    "objectives": {
        "title": "Learning Objectives",
        "default_content": [
            "Identify the key idea related to {theme_keyword}.",
            "Use 3 to 5 target expressions in classroom tasks.",
            "Complete one spoken or written output with clear support.",
        ],
        "refresh_content": [
            "Explain the main topic of {course_title} in clear English.",
            "Apply target language to one guided classroom task.",
            "Give a short response with evidence or examples.",
        ],
        "teacher_notes": "Read the objectives aloud and ask students which goal may be the most challenging today.",
        "refresh_notes": "Let students underline the action verbs in the objectives before the lesson begins.",
        "teaching_purpose": "Clarify measurable outcomes for the lesson.",
        "estimated_time": "3 minutes",
        "interaction_type": "Teacher-student interaction",
    },
    "key_points": {
        "title": "Key Points",
        "default_content": [
            "Understand the core content of {course_title}.",
            "Use the lesson language with accurate meaning and form.",
            "Finish the main classroom task with teamwork and evidence.",
        ],
        "refresh_content": [
            "Focus on the central meaning of the lesson materials.",
            "Notice useful expressions and sentence patterns for output.",
            "Prepare for the final task with accurate ideas and language.",
        ],
        "teacher_notes": "Point out the two or three priorities so students know where to concentrate their attention.",
        "refresh_notes": "Turn each key point into a short success criterion students can check later.",
        "teaching_purpose": "Highlight the major learning targets of the lesson.",
        "estimated_time": "2 minutes",
        "interaction_type": "Teacher guidance",
    },
    "difficult_points": {
        "title": "Difficult Points",
        "default_content": [
            "Explain ideas in complete English rather than single words.",
            "Use target language accurately in context.",
            "{level_support}",
        ],
        "refresh_content": [
            "Move from understanding to independent output.",
            "Connect evidence, language, and opinion clearly.",
            "{level_support}",
        ],
        "teacher_notes": "Tell students that the difficult points are normal and will be solved through guided practice.",
        "refresh_notes": "Model one difficult point first, then let students try with sentence frames.",
        "teaching_purpose": "Make learning challenges visible and manageable.",
        "estimated_time": "2 minutes",
        "interaction_type": "Teacher scaffolding",
    },
    "lead_in": {
        "title": "Lead-in",
        "default_content": [
            "Look at the lesson title: {course_title}.",
            "Share one fact or experience connected to {theme_keyword}.",
            "Predict what we may learn or discuss today.",
        ],
        "refresh_content": [
            "Read a quick question: Why does {theme_keyword} matter to teenagers?",
            "Think for 20 seconds and compare ideas with a partner.",
            "Choose one idea to report to the class.",
        ],
        "teacher_notes": "Use think-pair-share to activate background knowledge before the core task.",
        "refresh_notes": "Keep the pace quick and invite one confident group to model responses.",
        "teaching_purpose": "Activate prior knowledge and raise classroom interest.",
        "estimated_time": "4 minutes",
        "interaction_type": "Pair work",
    },
    "prediction": {
        "title": "Prediction",
        "default_content": [
            "Look at the title, pictures, and key words.",
            "Predict the topic and possible structure of the text.",
            "Write one guiding question for reading.",
        ],
        "refresh_content": [
            "Use the title and subheadings to make a quick prediction.",
            "Decide what information you expect to find in the text.",
            "Share your prediction with another pair.",
        ],
        "teacher_notes": "Collect two or three predictions and connect them to the reading purpose.",
        "refresh_notes": "Push students to explain why they made each prediction, not only what they predicted.",
        "teaching_purpose": "Build an efficient reading purpose before detailed processing.",
        "estimated_time": "4 minutes",
        "interaction_type": "Prediction task",
    },
    "fast_reading": {
        "title": "Fast Reading",
        "default_content": [
            "Skim the text in 2 minutes.",
            "Match each paragraph with its main idea.",
            "Choose the best summary sentence.",
        ],
        "refresh_content": [
            "Read for gist and ignore minor unknown words.",
            "Underline topic sentences or repeated ideas.",
            "Compare your main idea with your partner.",
        ],
        "teacher_notes": "Remind students to focus on main ideas instead of translating every sentence.",
        "refresh_notes": "Time the task strictly so students learn to skim efficiently.",
        "teaching_purpose": "Train students to identify gist quickly.",
        "estimated_time": "6 minutes",
        "interaction_type": "Individual work",
    },
    "careful_reading": {
        "title": "Careful Reading",
        "default_content": [
            "Read again and locate key details.",
            "Answer: What happens, why, and with what result?",
            "Mark evidence that supports your answers.",
        ],
        "refresh_content": [
            "Reread the important paragraphs carefully.",
            "Complete a detail chart with evidence from the text.",
            "Discuss one inference question in pairs.",
        ],
        "teacher_notes": "Guide students to support answers with evidence from the text instead of guessing.",
        "refresh_notes": "Pause after each question and ask students where the answer is found in the text.",
        "teaching_purpose": "Improve detail reading, inference, and evidence use.",
        "estimated_time": "8 minutes",
        "interaction_type": "Question answering",
    },
    "vocabulary_support": {
        "title": "Vocabulary Support",
        "default_content": [
            "Target words: topic, evidence, response, support.",
            "Match each word or phrase with a simple meaning.",
            "Use one expression to make a sentence about {theme_keyword}.",
        ],
        "refresh_content": [
            "Notice useful expressions from the lesson materials.",
            "Choose the best word to complete each sentence.",
            "Try one sentence frame for output practice.",
        ],
        "teacher_notes": "Keep explanations brief and move quickly to contextualized sentence practice.",
        "refresh_notes": "Invite students to paraphrase meanings in simple English before giving the answer.",
        "teaching_purpose": "Support comprehension and later output with usable language.",
        "estimated_time": "5 minutes",
        "interaction_type": "Language support",
    },
    "task_design": {
        "title": "Task Design",
        "default_content": [
            "Task: complete a {final_product}.",
            "Collect two key ideas and one supporting example from today's input.",
            "Organize your answer with clear language and evidence.",
            "Share your final response with a partner and revise one sentence.",
        ],
        "refresh_content": [
            "Final task: create a {final_product}.",
            "Use at least 2 target expressions from this lesson.",
            "Include one clear reason or example.",
            "Check the rubric before you share.",
        ],
        "teacher_notes": "Explain the success criteria before students begin the task.",
        "refresh_notes": "Show one brief model so students know the expected output level.",
        "teaching_purpose": "Connect lesson input to a concrete classroom task.",
        "estimated_time": "5 minutes",
        "interaction_type": "Task-based learning",
    },
    "classroom_interaction": {
        "title": "Classroom Interaction",
        "default_content": [
            "Discuss in groups: {interaction_prompt}",
            "Choose one speaker and one note taker.",
            "Be ready to share one group answer with the class.",
        ],
        "refresh_content": [
            "Work with your group on this challenge: {interaction_prompt}",
            "Use sentence starters to support quieter students.",
            "Prepare a 30-second class report.",
        ],
        "teacher_notes": "Circulate during the activity and support groups with prompts instead of full answers.",
        "refresh_notes": "Cold-call one or two groups after preparation so interaction leads to visible output.",
        "teaching_purpose": "Create meaningful student talk and collaborative thinking.",
        "estimated_time": "6 minutes",
        "interaction_type": "Group work",
    },
    "summary": {
        "title": "Summary",
        "default_content": [
            "Today we learned the key idea of {course_title}.",
            "We practiced target language for {final_product}.",
            "We checked evidence, language, and interaction together.",
        ],
        "refresh_content": [
            "Review: topic, key language, and final task.",
            "Complete the sentence: Today I can now...",
            "Name one strategy you will keep using after class.",
        ],
        "teacher_notes": "Let students summarize first, then use your summary to close gaps.",
        "refresh_notes": "Ask students to point back to the objectives and self-check their progress.",
        "teaching_purpose": "Consolidate what students have achieved in the lesson.",
        "estimated_time": "3 minutes",
        "interaction_type": "Student reflection",
    },
    "homework": {
        "title": "Homework",
        "default_content": [
            "Review today's target words and expressions.",
            "Finish or improve your {final_product}.",
            "{homework_extension}",
        ],
        "refresh_content": [
            "Polish your class output with better examples or language.",
            "Read the lesson material again and annotate key evidence.",
            "{homework_extension}",
        ],
        "teacher_notes": "State the product, length, and quality requirement clearly before students leave.",
        "refresh_notes": "Point out one required language item students must include in homework.",
        "teaching_purpose": "Extend learning beyond the classroom with focused follow-up work.",
        "estimated_time": "2 minutes",
        "interaction_type": "Assignment",
    },
    "blackboard_design": {
        "title": "Blackboard Design",
        "default_content": [
            "{course_title}",
            "Theme: {theme_keyword}",
            "Key language -> Evidence -> Output",
            "Task product: {final_product}",
        ],
        "refresh_content": [
            "{course_title}",
            "Topic + language + evidence + response",
            "Useful expressions: because / for example / in my opinion",
            "Output goal: {final_product}",
        ],
        "teacher_notes": "Use this structure to keep classroom board work clear and easy to follow.",
        "refresh_notes": "Write only the most reusable language on the board to avoid overload.",
        "teaching_purpose": "Provide a concise board plan for lesson organization.",
        "estimated_time": "1 minute",
        "interaction_type": "Teacher presentation",
    },
    "grammar_discovery": {
        "title": "Observe and Discover",
        "default_content": [
            "Read the example sentences carefully.",
            "Underline the target grammar pattern.",
            "Discuss what changes in form and meaning.",
        ],
        "refresh_content": [
            "Compare two example sentences from the lesson.",
            "Notice tense, structure, or function changes.",
            "Say the rule in your own words.",
        ],
        "teacher_notes": "Let students notice the grammar pattern before you explain the rule directly.",
        "refresh_notes": "Accept partial observations first, then guide students to a complete rule.",
        "teaching_purpose": "Lead students to discover grammar through examples.",
        "estimated_time": "5 minutes",
        "interaction_type": "Guided discovery",
    },
    "grammar_rule": {
        "title": "Grammar Rule",
        "default_content": [
            "Form: identify the sentence pattern clearly.",
            "Meaning: explain when and why it is used.",
            "Signal words or common mistakes to avoid.",
        ],
        "refresh_content": [
            "Summarize the form with one clear model sentence.",
            "Notice the function of the structure in context.",
            "Keep one quick warning about a common error.",
        ],
        "teacher_notes": "Keep rule explanation concise and always tie it back to meaningful examples.",
        "refresh_notes": "Ask students to transform one example sentence after the rule is explained.",
        "teaching_purpose": "Clarify the grammar rule for accurate later practice.",
        "estimated_time": "5 minutes",
        "interaction_type": "Teacher explanation",
    },
    "guided_practice": {
        "title": "Guided Practice",
        "default_content": [
            "Complete the sentence frames with the target grammar.",
            "Check answers with a partner.",
            "Explain why your answer is correct.",
        ],
        "refresh_content": [
            "Fill in the blanks using the target structure.",
            "Compare answers and correct one another.",
            "Read one answer aloud with confidence.",
        ],
        "teacher_notes": "Provide quick feedback and keep practice tightly linked to the rule.",
        "refresh_notes": "Use choral checking for the first item, then release students to work independently.",
        "teaching_purpose": "Support students while they first apply the new structure.",
        "estimated_time": "6 minutes",
        "interaction_type": "Pair checking",
    },
    "controlled_practice": {
        "title": "Controlled Practice",
        "default_content": [
            "Rewrite or combine sentences with the target grammar.",
            "Complete a short accuracy task.",
            "Check one common error together.",
        ],
        "refresh_content": [
            "Transform the sentences into the required pattern.",
            "Spot and correct grammar mistakes.",
            "Explain the correction rule in one sentence.",
        ],
        "teacher_notes": "Choose examples that reveal common mistakes and explain why those mistakes happen.",
        "refresh_notes": "Invite one student to explain an answer on the board.",
        "teaching_purpose": "Improve grammar accuracy through focused practice.",
        "estimated_time": "6 minutes",
        "interaction_type": "Controlled practice",
    },
    "writing_task_analysis": {
        "title": "Writing Task Analysis",
        "default_content": [
            "Read the writing prompt carefully.",
            "Identify purpose, audience, and key points.",
            "List the information that must be included.",
        ],
        "refresh_content": [
            "Circle task words in the writing prompt.",
            "Decide the text type and writing goal.",
            "Check what evidence or examples are needed.",
        ],
        "teacher_notes": "Show students how to unpack the prompt before they start writing.",
        "refresh_notes": "Ask students which instruction in the prompt is most important and why.",
        "teaching_purpose": "Help students understand the writing task before drafting.",
        "estimated_time": "5 minutes",
        "interaction_type": "Task analysis",
    },
    "useful_expressions": {
        "title": "Useful Expressions",
        "default_content": [
            "Use sentence starters for clear organization.",
            "Add linking words such as first, besides, and finally.",
            "Prepare one expression for opinion and one for example.",
        ],
        "refresh_content": [
            "Collect useful chunks for beginning, supporting, and ending writing.",
            "Match each expression with the right writing purpose.",
            "Try one sentence using a new phrase.",
        ],
        "teacher_notes": "Keep expressions practical so students can immediately reuse them in the task.",
        "refresh_notes": "Ask students to choose two expressions they will definitely use in their writing.",
        "teaching_purpose": "Provide language support for classroom writing output.",
        "estimated_time": "5 minutes",
        "interaction_type": "Language support",
    },
    "writing_structure": {
        "title": "Structure Building",
        "default_content": [
            "Plan an opening, body, and ending.",
            "Decide what idea belongs in each part.",
            "Use a simple outline before drafting.",
        ],
        "refresh_content": [
            "Organize your paragraph or essay with a clear structure.",
            "Write one topic sentence for the main part.",
            "Add one supporting detail or example.",
        ],
        "teacher_notes": "Model the structure visually so students can imitate it during drafting.",
        "refresh_notes": "Let students complete a mini-outline before they write full sentences.",
        "teaching_purpose": "Support coherent organization in student writing.",
        "estimated_time": "5 minutes",
        "interaction_type": "Teacher modeling",
    },
    "sample_appreciation": {
        "title": "Sample Appreciation",
        "default_content": [
            "Read the model writing quickly.",
            "Find one strong idea and one useful expression.",
            "Discuss why the sample is effective.",
        ],
        "refresh_content": [
            "Notice how the sample uses structure and details.",
            "Highlight one sentence worth imitating.",
            "Say what you can borrow for your own writing.",
        ],
        "teacher_notes": "Do not over-explain the sample; focus students on what they can transfer to their own work.",
        "refresh_notes": "Keep the sample brief and emphasize imitation of good moves, not memorization.",
        "teaching_purpose": "Use a model text to make quality expectations visible.",
        "estimated_time": "4 minutes",
        "interaction_type": "Text appreciation",
    },
    "guided_writing": {
        "title": "Guided Writing",
        "default_content": [
            "Draft your response with the outline and expressions.",
            "Check if each sentence supports the task goal.",
            "Finish a short first version in class.",
        ],
        "refresh_content": [
            "Write with sentence frames if needed.",
            "Pause to check language, structure, and examples.",
            "Underline one sentence you want feedback on.",
        ],
        "teacher_notes": "Walk around while students write and provide fast, targeted support.",
        "refresh_notes": "Prioritize feedback on task completion and organization before minor errors.",
        "teaching_purpose": "Turn writing support into independent student production.",
        "estimated_time": "8 minutes",
        "interaction_type": "Independent writing",
    },
    "pre_listening": {
        "title": "Pre-listening",
        "default_content": [
            "Preview the topic and key words before listening.",
            "Predict who is speaking and what the situation is.",
            "Listen with one guiding question in mind.",
        ],
        "refresh_content": [
            "Look at the listening cues and topic words.",
            "Guess the situation and possible opinions.",
            "Set one purpose for the first listening.",
        ],
        "teacher_notes": "Keep preview time short so students stay focused on the listening task itself.",
        "refresh_notes": "Ask one prediction question, then move straight into the audio task.",
        "teaching_purpose": "Reduce listening difficulty by activating key context first.",
        "estimated_time": "4 minutes",
        "interaction_type": "Teacher guidance",
    },
    "while_listening": {
        "title": "While-listening",
        "default_content": [
            "Listen for the main idea first.",
            "Listen again and complete the note chart.",
            "Check answers with evidence from the audio.",
        ],
        "refresh_content": [
            "Use the first listening for gist.",
            "Use the second listening for key details.",
            "Compare answers with a partner before whole-class feedback.",
        ],
        "teacher_notes": "Separate gist and detail listening so students are not overloaded by too many demands at once.",
        "refresh_notes": "Pause between listenings and restate the next listening purpose clearly.",
        "teaching_purpose": "Train students to listen for both overall meaning and key details.",
        "estimated_time": "8 minutes",
        "interaction_type": "Listening task",
    },
    "post_listening": {
        "title": "Post-listening",
        "default_content": [
            "Summarize the speaker's main point.",
            "Explain one detail that supports the message.",
            "Connect the audio to your own experience or opinion.",
        ],
        "refresh_content": [
            "Retell the key information in 2 or 3 sentences.",
            "Discuss one follow-up question with a partner.",
            "Prepare to use the listening input in a speaking task.",
        ],
        "teacher_notes": "Bridge the listening input to output so students use what they heard meaningfully.",
        "refresh_notes": "Ask students to retell before giving your own summary.",
        "teaching_purpose": "Transform listening input into understanding and output.",
        "estimated_time": "5 minutes",
        "interaction_type": "Pair discussion",
    },
    "speaking_task": {
        "title": "Speaking Task",
        "default_content": [
            "Use the listening input to complete a short speaking task.",
            "Include one opinion and one supporting reason.",
            "Practice with a partner before sharing.",
        ],
        "refresh_content": [
            "Prepare a short spoken response with sentence starters.",
            "Use one key word and one useful expression.",
            "Share your answer with your group.",
        ],
        "teacher_notes": "Provide sentence starters so weaker students can still participate confidently.",
        "refresh_notes": "Choose a realistic speaking prompt that directly uses the listening content.",
        "teaching_purpose": "Extend listening work into spoken classroom performance.",
        "estimated_time": "6 minutes",
        "interaction_type": "Speaking practice",
    },
    "knowledge_review": {
        "title": "Knowledge Review",
        "default_content": [
            "Review the main ideas from recent lessons.",
            "Sort key knowledge into categories or themes.",
            "Recall one example for each category.",
        ],
        "refresh_content": [
            "Brainstorm what we have learned in this unit.",
            "Use a quick chart to organize old knowledge.",
            "Identify one area that still needs revision.",
        ],
        "teacher_notes": "Keep review active by asking students to retrieve knowledge before you explain.",
        "refresh_notes": "Use quick retrieval prompts instead of long explanation to keep the pace high.",
        "teaching_purpose": "Reactivate prior learning before integrated revision tasks.",
        "estimated_time": "5 minutes",
        "interaction_type": "Knowledge activation",
    },
    "grammar_review": {
        "title": "Grammar Review",
        "default_content": [
            "Review the unit grammar focus with examples.",
            "Complete one quick correction activity.",
            "Explain why the correct form works.",
        ],
        "refresh_content": [
            "Recall the grammar rule from memory.",
            "Fix mistakes in short example sentences.",
            "Summarize one exam reminder.",
        ],
        "teacher_notes": "Choose only the most important revision points rather than reteaching everything.",
        "refresh_notes": "Use errors students often make so the review stays practical.",
        "teaching_purpose": "Refresh the core grammar needed for revision tasks.",
        "estimated_time": "5 minutes",
        "interaction_type": "Grammar revision",
    },
    "integrated_task": {
        "title": "Integrated Task",
        "default_content": [
            "Use reading, vocabulary, and grammar together.",
            "Solve one integrated problem or mini project.",
            "Show both understanding and language accuracy.",
        ],
        "refresh_content": [
            "Complete a mixed-skill challenge in pairs or groups.",
            "Use unit knowledge to support your final answer.",
            "Prepare one concise class report.",
        ],
        "teacher_notes": "Make the task feel like a mini performance so revision leads to visible application.",
        "refresh_notes": "Encourage students to explain how they used old knowledge in the new task.",
        "teaching_purpose": "Promote transfer of reviewed knowledge into a new challenge.",
        "estimated_time": "7 minutes",
        "interaction_type": "Integrated practice",
    },
}


def normalize_lesson_type(lesson_type):
    text = (lesson_type or "reading").strip().lower()
    if "grammar" in text:
        return "grammar"
    if "writing" in text:
        return "writing"
    if "listening" in text or "speaking" in text:
        return "listening_speaking"
    if "revision" in text or "review" in text:
        return "revision"
    return "reading"


def build_context(task):
    style = task.get("style") or "常规课"
    student_level = task.get("student_level") or "中等"
    course_title = task.get("course_title") or "Senior English Lesson"
    lesson_type_display = task.get("lesson_type") or "Reading"
    theme_keyword = course_title.split()[-1].strip(".,!?") if course_title.strip() else "the topic"

    if student_level == "基础薄弱":
        level_support = "Use sentence starters and bilingual hints when necessary."
    elif student_level == "较好":
        level_support = "Push students to explain ideas with fuller evidence and more precise language."
    else:
        level_support = "Give brief scaffolds, then move students toward independent answers."

    if style == "公开课":
        interaction_prompt = "How can your group show a clear idea and one strong example for the open lesson?"
    elif style == "复习课":
        interaction_prompt = "Which knowledge point is most useful for revision, and how will you apply it?"
    else:
        interaction_prompt = "What is your group's best answer, and what evidence supports it?"

    lesson_key = normalize_lesson_type(lesson_type_display)
    final_product_map = {
        "reading": "short reading response",
        "grammar": "grammar-based mini output",
        "writing": "guided writing draft",
        "listening_speaking": "spoken response",
        "revision": "revision task answer",
    }
    homework_map = {
        "reading": "Write 4 to 5 sentences about the reading topic.",
        "grammar": "Finish a short grammar exercise and create 3 original sentences.",
        "writing": "Revise your draft and improve it with clearer examples.",
        "listening_speaking": "Practice the speaking task aloud and record one stronger version.",
        "revision": "Sort today's revision notes and finish one mixed practice set.",
    }

    return {
        "course_title": course_title,
        "unit": task.get("unit") or "Unit 1",
        "lesson_type_display": lesson_type_display,
        "grade": task.get("grade") or "Senior One",
        "textbook": task.get("textbook") or "PEP",
        "theme_keyword": theme_keyword,
        "level_support": level_support,
        "interaction_prompt": interaction_prompt,
        "final_product": final_product_map.get(lesson_key, "classroom output"),
        "homework_extension": homework_map.get(lesson_key, "Preview the next lesson and note one question."),
    }


def format_template(value, context):
    if isinstance(value, list):
        return [item.format(**context) for item in value]
    return value.format(**context)


def build_slide(task, slide_type, slide_index, regenerate=False):
    context = build_context(task)
    spec = SLIDE_LIBRARY.get(slide_type, SLIDE_LIBRARY["summary"])
    content_key = "refresh_content" if regenerate else "default_content"
    notes_key = "refresh_notes" if regenerate else "teacher_notes"

    return {
        "slide_index": slide_index,
        "slide_type": slide_type,
        "title": format_template(spec["title"], context),
        "visible_content": format_template(spec[content_key], context),
        "teacher_notes": format_template(spec[notes_key], context),
        "teaching_purpose": format_template(spec["teaching_purpose"], context),
        "estimated_time": spec["estimated_time"],
        "interaction_type": spec["interaction_type"],
    }


def generate_mock_slides(task):
    lesson_key = normalize_lesson_type(task.get("lesson_type"))
    outline = OUTLINE_MAP.get(lesson_key, OUTLINE_MAP["reading"])
    return [
        build_slide(task, slide_type, slide_index)
        for slide_index, slide_type in enumerate(outline, start=1)
    ]


def regenerate_mock_slide(task, current_slide):
    return build_slide(
        task,
        current_slide.get("slide_type") or "summary",
        current_slide.get("slide_index") or 1,
        regenerate=True,
    )
