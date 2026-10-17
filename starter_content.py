"""
Starter training videos (YouTube links found Oct 2026) and starter quizzes.

Quiz questions cover badminton fundamentals for each topic, so they stay
correct even though they were written separately from the videos. Coaches can
edit or replace any of these inside the app. `min_watch` is a floor (minutes)
the in-app player always requires on top of 95% of the real video length.
"""

# (title, url, category, level, min_watch)
OPTIONAL = [
    ("6 Corners Footwork for Badminton (Basic)", "https://www.youtube.com/watch?v=a7ajExQKOvY", "Footwork", "Beginner", 1),
    ("Improve Badminton Footwork in 10 Minutes", "https://www.youtube.com/watch?v=T6gZMcFYZNo", "Footwork", "Intermediate", 1),
    ("Footwork Training: Beginner to Advanced", "https://www.youtube.com/watch?v=dFU1nvCE8p4", "Footwork", "Expert", 1),
    ("Perfect Badminton Clear — 6 Basic Steps", "https://www.youtube.com/watch?v=vqZ7A9mp1ds", "Shots", "Beginner", 1),
    ("How to Play the Perfect Drop Shot", "https://www.youtube.com/watch?v=bviWoAQ_LDo", "Shots", "Intermediate", 1),
    ("Backhand Clear, Drop & Smash", "https://www.youtube.com/watch?v=jCKx70__4ec", "Shots", "Expert", 1),
    ("Learn the Jump Smash — Step by Step", "https://www.youtube.com/watch?v=uPF7KQ-PX7k", "Shots", "Expert", 1),
    ("Forehand and Backhand Grip", "https://www.youtube.com/watch?v=v8UYUiiJgV0", "Grip", "Beginner", 1),
    ("Grip Change: Forehand to Backhand", "https://www.youtube.com/watch?v=DhXTGwXVzZM", "Grip", "Intermediate", 1),
    ("Grips: Forehand, Backhand, Bevel & Panhandle", "https://www.youtube.com/watch?v=AV2DDa-1w4A", "Grip", "Expert", 1),
    ("Home Plyometrics Workout for Badminton Players", "https://www.youtube.com/watch?v=lZu89rrVSQ0", "Plyometrics", "Beginner", 1),
    ("7 Plyometric Exercises for Speed & Explosiveness", "https://www.youtube.com/watch?v=Y3cwWyavgus", "Plyometrics", "Intermediate", 1),
    ("The 10 Best Plyometrics to Be Explosive", "https://www.youtube.com/watch?v=lLCiLxHlTGY", "Plyometrics", "Expert", 1),
]


def _q(question, options, answer):
    return {"q": question, "options": options, "answer": answer}


# (title, url, category, level, min_watch, questions)
QUIZZES = [
    ("How to Hold the Forehand & Backhand Grip", "https://www.youtube.com/watch?v=46Vldv0WTqE", "Grip", "Beginner", 1, [
        _q("How should the basic forehand grip feel?",
           ["Like shaking hands with the racket, relaxed", "A tight fist around the handle",
            "Fingertips only, racket face flat like a frying pan", "Thumb wrapped over the frame"], 0),
        _q("In the basic backhand (thumb) grip, where does your thumb go?",
           ["Wrapped around your fingers", "Flat on the wide back bevel of the handle",
            "On the strings", "It doesn't touch the handle"], 1),
        _q("Why keep your grip loose between shots?",
           ["It looks better", "So you can change grips fast and squeeze for power at contact",
            "So the racket doesn't wear out", "It makes the shuttle go slower"], 1),
        _q("When should you switch to the backhand grip?",
           ["Only when serving", "Never — use one grip for everything",
            "When the shuttle comes to your non-racket side", "Only for smashes"], 2),
        _q("Using a flat 'frying pan' grip for every shot mostly limits your…",
           ["Power and reach on overhead and backhand shots", "Footwork speed",
            "Ability to serve legally", "Nothing — it's the best grip"], 0),
    ]),
    ("Footwork Basics for Beginners", "https://www.youtube.com/watch?v=NhNEEcLPjpc", "Footwork", "Beginner", 1, [
        _q("What is a split step?",
           ["A lunge to the net", "A small hop that lands as your opponent hits, so you can push off any way",
            "Crossing your feet to run sideways", "A jump smash"], 1),
        _q("In singles, where is your base position?",
           ["Right at the net", "Near the back line", "Around the middle of the court",
            "Wherever you last hit from"], 2),
        _q("A right-handed player lunging to the net should lead with which foot?",
           ["Left foot", "Right (racket-side) foot", "Both feet together", "It doesn't matter"], 1),
        _q("What should you do right after every shot?",
           ["Watch where it lands", "Recover back toward your base", "Change grips and wait",
            "Stay where you are"], 1),
        _q("A chassé step means…",
           ["Side-shuffling where the feet come together but don't cross", "Running with crossed feet",
            "Jumping on one leg", "Walking backward"], 0),
    ]),
    ("How to Play the Perfect Smash", "https://www.youtube.com/watch?v=faG2NWIVM18", "Shots", "Intermediate", 1, [
        _q("Where is the best contact point for a smash?",
           ["Low, beside your hip", "High and slightly in front of your body",
            "Behind your head", "At shoulder height to the side"], 1),
        _q("Where does most smash power come from?",
           ["Only the arm muscles", "Body rotation plus fast forearm rotation and a whip at contact",
            "Gripping as tight as possible the whole time", "Jumping as high as you can"], 1),
        _q("What does the non-racket arm do?",
           ["Stays at your side", "Points up for balance and aim, then pulls down as you swing",
            "Holds the racket too", "Covers your face"], 1),
        _q("Why hit the smash steeply downward?",
           ["So it goes out", "So it lands fast and is hard to return", "To make it float",
            "It doesn't matter"], 1),
        _q("After you smash, you should…",
           ["Admire the shot", "Get ready to move forward — returns often come short or flat",
            "Run to the back line", "Turn around"], 1),
    ]),
    ("8 Plyometric Exercises for Badminton", "https://www.youtube.com/watch?v=msX4T_VcwCI", "Plyometrics", "Intermediate", 1, [
        _q("What are plyometrics?",
           ["Slow stretching", "Explosive jumping and bounding drills that build fast power",
            "Long-distance running", "Weightlifting only"], 1),
        _q("How do plyometrics help in badminton?",
           ["Quicker first step, higher jumps and faster direction changes", "Stronger grip only",
            "Better hand-eye coordination only", "They don't"], 0),
        _q("What is the safest way to land?",
           ["Straight-legged on your heels", "Softly on the balls of your feet with knees bent",
            "On one foot with locked knee", "Flat-footed and stiff"], 1),
        _q("What should you do before a plyometric workout?",
           ["Nothing", "A proper warm-up", "Eat a big meal", "Hold long static stretches only"], 1),
        _q("Which is better for plyometrics?",
           ["Endless reps when tired", "Short sets at full effort with rest in between",
            "One very long set", "Going as slow as possible"], 1),
    ]),
]


QUIZZES.append(
    ("Backhand Smash (Expert)", "https://www.youtube.com/watch?v=-H0-PLLgyQ4", "Shots", "Expert", 1, [
        _q("Which grip is usually used for an overhead backhand smash?",
           ["Panhandle (frying-pan) grip", "Thumb grip, with the thumb on the wide bevel",
            "Two-handed grip", "Forehand grip with a straight wrist"], 1),
        _q("Where should you contact the shuttle on an overhead backhand?",
           ["Behind your body, low", "High and slightly in front, with your back to the net",
            "At waist height facing the net", "Directly overhead while facing the net"], 1),
        _q("Most of a backhand's power comes from…",
           ["A big backswing of the whole arm only", "Fast forearm rotation (supination) and a thumb push at contact",
            "Jumping as high as possible", "Hitting with a locked wrist"], 1),
        _q("Why is a backhand smash an advanced shot?",
           ["It's illegal for beginners", "It needs precise timing, grip and footwork to generate power from a weak side",
            "It can only be hit in doubles", "It always goes out"], 1),
        _q("After an overhead backhand, the first thing to do is…",
           ["Keep facing the back wall", "Turn and recover quickly toward base",
            "Change racket hands", "Wait to see where it lands"], 1),
    ]))
QUIZZES.append(
    ("Footwork Training: Beginner to Advanced", "https://www.youtube.com/watch?v=dFU1nvCE8p4", "Footwork", "Expert", 1, [
        _q("Advanced players time their split step so they land…",
           ["Before the opponent starts their swing", "Right as the opponent hits the shuttle",
            "After the shuttle crosses the net", "Only on serves"], 1),
        _q("Why do advanced players use a jump or scissor kick at the back court?",
           ["To look stylish", "To hit earlier and recover faster toward base", "Because it's required",
            "To slow the rally down"], 1),
        _q("What makes footwork 'efficient'?",
           ["Taking as many tiny steps as possible", "The fewest, fastest steps that keep you balanced",
            "Always running straight lines", "Standing still and reaching"], 1),
        _q("In a deep lunge to the net, your front knee should…",
           ["Collapse inward", "Point the same way as your toes, over the foot",
            "Stay perfectly straight", "Touch the floor"], 1),
        _q("A good way to make footwork faster is…",
           ["Shadow footwork drills at match intensity with rest", "Only playing matches",
            "Wearing heavier shoes", "Skipping the warm-up"], 0),
    ]))


def load_starters(store, kind: str) -> int:
    """Adds starter videos of one kind ('optional' or 'quiz') not already in the
    library. Returns how many were added."""
    have = {v["url"] for v in store.data["videos"] if v["kind"] == kind}
    added = 0
    if kind == "optional":
        for title, url, cat, level, mins in OPTIONAL:
            if url not in have:
                store.save_video(None, "optional", title, url, cat, mins,
                                 store.default_video_points("optional", level), level=level)
                added += 1
    else:
        for title, url, cat, level, mins, qs in QUIZZES:
            if url not in have:
                store.save_video(None, "quiz", title, url, cat, mins,
                                 store.default_video_points("quiz", level), qs, level=level)
                added += 1
    return added
