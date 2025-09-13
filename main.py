const API_URL = 'https://career-guidance-api-97tg.onrender.com';

// State variables to manage the quiz flow
let currentPhase = 'general';
let questions = [];
let currentQuestionIndex = 0;
let allAnswersForAI = [];

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('quiz-area')) {
        startQuiz();
    }
});

function startQuiz() {
    fetchQuestions(API_URL + '/api/quiz/start');
}

async function fetchQuestions(url, options = {}) {
    const quizArea = document.getElementById('quiz-area');
    quizArea.innerHTML = '<div class="loader"></div>';
    try {
        const response = await fetch(url, options);
        // Add a check for a successful response
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        questions = [...questions, ...data.questions];
        
        // This was a bug. The index should not be reset, it should continue
        // from where it left off, but since we are showing question by question,
        // we start with the first new question. This is handled by nextStep logic.
        
        renderCurrentQuestion();
    } catch (error) {
        console.error("Error fetching questions:", error);
        const quizContainer = document.querySelector('.quiz-container');
        quizContainer.innerHTML = '<p style="text-align: center; color: red;">Could not load the next part of the quiz. Please refresh and try again.</p>';
    }
}

function renderCurrentQuestion() {
    const quizArea = document.getElementById('quiz-area');
    quizArea.innerHTML = ''; // Clear loader or previous question

    if (currentQuestionIndex >= questions.length) {
        return; // Should not happen, handled by nextStep
    }

    const q = questions[currentQuestionIndex];
    
    const questionSlide = document.createElement('div');
    questionSlide.className = 'question-slide active';

    let optionsHTML = '<div class="options-grid">';
    q.options.forEach(opt => {
        const category = opt.category || '';
        optionsHTML += `<button class="option-btn" data-category="${category}">${opt.text}</button>`;
    });
    optionsHTML += '</div>';

    questionSlide.innerHTML = `<h2 id="question-text">${q.question}</h2>` + optionsHTML;
    quizArea.appendChild(questionSlide);

    updateProgressBar();
    addOptionListeners();
}

function addOptionListeners() {
    document.querySelectorAll('.option-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const selectedText = btn.textContent;
            const selectedCategory = btn.dataset.category;
            const currentQuestion = questions[currentQuestionIndex];
            
            // Save the answer with the question ID
            allAnswersForAI.push({
                questionId: currentQuestion.id,
                question: currentQuestion.question,
                answer: selectedText,
                category: selectedCategory
            });
            
            btn.classList.add('selected');
            document.querySelectorAll('.option-btn').forEach(b => b.disabled = true);
            
            setTimeout(nextStep, 400);
        });
    });
}

function nextStep() {
    const currentSlide = document.querySelector('.question-slide');
    if (currentSlide) {
        currentSlide.classList.add('exiting');
    }

    setTimeout(() => {
        currentQuestionIndex++;
        if (currentQuestionIndex < questions.length) {
            renderCurrentQuestion();
        } else {
            if (currentPhase === 'general') {
                currentPhase = 'specific';
                
                // **THE FIX IS HERE**
                // We create the payload from the answers we have stored
                const generalAnswers = allAnswersForAI.map(ans => ({
                    questionId: ans.questionId,
                    selectedCategory: ans.category
                })).filter(ans => ans.questionId && ans.selectedCategory); // Ensure we only send valid entries

                fetchQuestions(API_URL + '/api/quiz/next', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ answers: generalAnswers })
                });
            } else {
                submitToAI();
            }
        }
    }, 400);
}

async function submitToAI() {
    const quizArea = document.getElementById('quiz-area');
    quizArea.innerHTML = '<div class="loader"></div><p style="text-align:center;">Sending to our AI counselor for analysis...</p>';

    const finalSubmission = allAnswersForAI.map(({ question, answer }) => ({ question, answer }));

    try {
        const response = await fetch(`${API_URL}/api/quiz/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ all_answers: finalSubmission })
        });
        if (!response.ok) { throw new Error('AI submission failed'); }
        const result = await response.json();
        const aiData = JSON.parse(result.data);
        displayResult(aiData);
    } catch (error) {
        console.error("Error submitting quiz:", error);
        quizArea.innerHTML = '<p>Sorry, there was an error generating your result.</p>';
    }
}

function updateProgressBar() {
    // A better progress logic for two phases
    let progress = 0;
    const totalGeneral = questions.filter(q => q.phase === 'general').length;
    const totalSpecific = 2; // We expect 2 specific questions
    const totalQuestions = totalGeneral + totalSpecific;

    if (currentPhase === 'general') {
        progress = (currentQuestionIndex / totalQuestions) * 100;
    } else {
        progress = ((totalGeneral + (currentQuestionIndex - totalGeneral)) / totalQuestions) * 100;
    }
    
    document.getElementById('progress-bar').style.width = `${Math.min(progress, 100)}%`;
}

function displayResult(data) {
    const quizContainer = document.querySelector('.quiz-container');
    const resultArea = document.getElementById('result-area');

    quizContainer.innerHTML = '';
    quizContainer.appendChild(resultArea);
    resultArea.classList.remove('hidden');
    resultArea.style.animation = 'slideIn 0.5s ease-out forwards';

    let careersHTML = '<ul>';
    data.suitable_careers.forEach(career => {
        careersHTML += `<li>${career}</li>`;
    });
    careersHTML += '</ul>';

    resultArea.innerHTML = `
        <h2>Your Personalized Recommendation</h2>
        <div class="stream-box">
            <h4>Primary Stream</h4>
            <p style="font-size: 1.5rem; font-weight: bold;">${data.recommended_stream}</p>
        </div>
        <p id="result-reason">"${data.reason}"</p>
        <div>
            <h3>Potential Career Paths</h3>
            ${careersHTML}
        </div>
    `;
}
