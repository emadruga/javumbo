import React from 'react';

// Basic styling (consider moving to CSS)
const cardStyle = {
  border: '1px solid #eee',
  padding: '20px',
  margin: '20px 0',
  minHeight: '150px',
  position: 'relative',
  backgroundColor: '#f9f9f9',
  borderRadius: '5px',
  textAlign: 'center',
};

const contentStyle = {
  fontSize: '1.2em',
  marginBottom: '20px',
};

const answerStyle = {
    ...contentStyle,
    borderTop: '1px dashed #ccc',
    paddingTop: '20px',
    marginTop: '20px',
    color: '#333'
};

const buttonContainerStyle = {
  marginTop: '15px',
  display: 'flex',
  justifyContent: 'space-around',
  gap: '10px'
};

const buttonStyle = {
    padding: '10px 15px',
    fontSize: '1em',
    cursor: 'pointer',
    borderRadius: '4px',
    border: '1px solid #ccc'
};

const againButtonStyle = {...buttonStyle, backgroundColor: '#dc3545', color: 'white'};
const hardButtonStyle = {...buttonStyle, backgroundColor: '#ffc107', color: 'black'};
const goodButtonStyle = {...buttonStyle, backgroundColor: '#28a745', color: 'white'};
const easyButtonStyle = {...buttonStyle, backgroundColor: '#17a2b8', color: 'white'};
const showAnswerButtonStyle = {...buttonStyle, backgroundColor: '#007bff', color: 'white'};


function Flashcard({ cardData, showAnswer, /* answerContent, */ onShowAnswer, onAnswer }) {
  if (!cardData) {
    return <div style={cardStyle}>Loading card...</div>;
  }

  return (
    <div style={cardStyle}>
      <div style={contentStyle}>{cardData.front}</div>

      {showAnswer ? (
        <>
          <div style={answerStyle}>{cardData.back}</div>
          <div style={buttonContainerStyle}>
            <button style={againButtonStyle} onClick={() => onAnswer(1)}>Again (1)</button>
            <button style={hardButtonStyle} onClick={() => onAnswer(2)}>Hard (2)</button>
            <button style={goodButtonStyle} onClick={() => onAnswer(3)}>Good (3)</button>
            <button style={easyButtonStyle} onClick={() => onAnswer(4)}>Easy (4)</button>
          </div>
        </>
      ) : (
        <button style={showAnswerButtonStyle} onClick={onShowAnswer}>Show Answer</button>
      )}
    </div>
  );
}

export default Flashcard; 