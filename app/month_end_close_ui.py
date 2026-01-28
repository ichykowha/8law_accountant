# app/month_end_close_ui.py
import streamlit as st
from backend.month_end_close import (
    get_checklist, complete_task, auto_complete_tasks, generate_summary_report,
    send_reminder, get_outstanding_tasks, get_ai_suggestions, detect_anomalies, get_task_help, get_progress,
    whats_missing, submit_feedback, get_timeline, predict_completion_date, get_bottlenecks, answer_question
)

st.title("Month-End Close Accelerator")

user_id = 1  # Demo user

st.info("Checklist is dynamically generated based on company type, anomalies, and AI suggestions.")


# What's missing feature
st.subheader("What's Missing?")
st.write(whats_missing(user_id))

# Timeline analytics
st.subheader("Timeline Analytics")
timeline = get_timeline(user_id)
for t in timeline:
    ts = t['timestamp']
    ts_str = time.ctime(ts) if ts else "Not completed"
    st.write(f"{t['task']}: {'✅' if t['completed'] else '❌'} | {ts_str}")

pred = predict_completion_date(user_id)
if pred:
    st.info(f"Predicted completion date: {time.ctime(pred)}")
bottlenecks = get_bottlenecks(user_id)
if bottlenecks:
    st.warning(f"Potential bottleneck: {', '.join(bottlenecks)}")

progress = get_progress(user_id)
st.progress(progress, text=f"Progress: {int(progress*100)}% complete")

if st.button("Auto-complete Routine Steps (AI/ML)"):
    auto_complete_tasks(user_id)
    st.success("Routine steps completed.")

checklist = get_checklist(user_id)

for t in checklist:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"{t['task']} | Completed: {t['completed']}")
        if t.get('help'):
            st.caption(f"Help: {t['help']}")
    with col2:
        if not t['completed'] and st.button(f"Mark as done", key=t['task']):
            complete_task(user_id, t['task'])
            st.success(f"Marked '{t['task']}' as completed.")

outstanding = get_outstanding_tasks(user_id)
if outstanding:
    st.warning(f"Outstanding tasks: {', '.join(outstanding)}")
    if st.button("Send Reminder Email"):
        # Demo email
        if send_reminder(user_id, "user@example.com"):
            st.success("Reminder sent!")
        else:
            st.info("No outstanding tasks to remind.")

anomalies = detect_anomalies(user_id)
if anomalies:
    st.error(f"Anomalies detected: {', '.join(anomalies)}")


# AI suggestion and feedback
ai_suggestion = get_ai_suggestions(user_id)
st.info(f"AI Suggestion: {ai_suggestion}")
with st.expander("Was this suggestion helpful?"):
    feedback = st.text_input("Your feedback", key="ai_feedback")
    if st.button("Submit Feedback") and feedback:
        submit_feedback(user_id, feedback)
        st.success("Thank you for your feedback!")

# Natural language Q&A
st.subheader("Ask 6law (AI Q&A)")
user_q = st.text_input("Ask a question about the close process, tasks, or requirements:", key="nlq")
if st.button("Get Answer") and user_q:
    answer = answer_question(user_id, user_q)
    st.success(f"6law says: {answer}")

if all(t['completed'] for t in checklist):
    st.success("Month-end close complete! You can now generate your summary report.")
    summary = generate_summary_report(user_id)
    st.download_button("Download Close Report", summary, file_name="month_end_close.txt")
    st.text_area("AI-Generated Summary", summary, height=200)
