from sqlmodel import Session

from backend.database.models import ChallengeEvaluations

"""
ADD TO MESSAGE TABLE
model: Optional[varchar] the model used for the message
is_user_provided: indicates whether the user provided the message
role: specify the role
type: varchar is the instance class name for parsing the content


CHALLENGE_EVALUATION_TABLE [COMPLETE]
challenge_context_id: int [foreign key]
succeed_at: int
processed_at: int
failed_at: int
errored_at: int
result: text
result_text: text
result_type: text


REMOVE FROM CHALLENGE TABLE
succeeded_at: int
failed_at: int

ADD TO CHALLENGE TABLE

# For simplicity's sake, all tools must be called for it to pass.
tool_calls: text # json formatted list of strings
evaluation_prompt # prompt used to evaluate

SET CAN CONTRIBUTE TO FALSE
can_contribute = False
"""



def _set_challenge_context_processed(session: Session, challenge_context_id: int):


    evaluation: ChallengeEvaluations = session.exec(select(ChallengeEvaluations).where(     
        challenge_context_id=challenge_context_id)).first()
    if evaluation.processed_at is not None:
        raise ValueError("Evaluation race condition")
    evaluation.processed_at = int(time.time())

    challenge_context: ChallengeContexts = session.select(ChallengeContexts).filter(     
        id=challenge_context_id).first()

    assert challenge_context, "Challenge must exist for evaluation. DB schema error?""
    challenge_context.can_contribute = False

    session.add(evaluation)
    session.add(challenge_context)
    session.commit()


def get_raw_message_instance(content: str, content_type: str) -> Any:
    pass


def format_as_messages(content: str, content_type: str) -> list[Message]:
    pass


def get_evaluation_result(
        session: Session, challenge_context: ChallengeUserContexts) -> EvalResult:
    # This challenge context does not have the messages in a user-available format by
    # default
    challenge: Challenges = challenge_context.challenges
    if challenge:
        get_tool_calls()
    if tool_call without prompt evaluation, then:
        check if the tool was called, if it was, then success

    if tool_call and prompt evaluation, then:
        check if the tool was called, and then evaluate the context

    pass


def evaluate_challenge_context(session: Session, challenge_context_id: int):
    evaluation: Evaluation = session.select(ChallengeContextEvaluation).filter(     
            challenge_context_id=challenge_context_id).first()

    if evaluation.processed_at is None:
        raise NotFoundError("Evaluation not found")

    with Locker().acquire_lock(challenge_context_id):
        challenge_context: ChallengeUserContexts = _set_challenge_context_processed(session, challenge_context_id)

    # Format the challenge context for evaluation.
    result_text: str = "not processed"
    result: Optional[str] = None

    now = int(time.time())

    try:
        eval_result: EvalResult = evaluate_challenge_context(session, challenge_context)
        assert eval_result in [eval_status.SUCCEEDED, eval_status.FAILED, \
                eval_status.ERRORED]
        if eval_result.status == eval_status.SUCCEEDED:
            evaluation.succeeded_at = now
        elif eval_result.status == eval_status.FAILED:
            evaluation.failed_at = now
        elif eval_result.status == eval_status.ERRORED:
            evaluation.errored_at = now
    except Exception as e:
        evaluation.errored_at = now
        result_text = str(e)
    finally:
        evaluation.result = result
        evaluation.result_text = result_text
        session.add(evaluation)
        session.commit()