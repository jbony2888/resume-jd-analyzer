Gap Analyzer App

A React application for analyzing the gap between Job Descriptions and Résumés using the Groq API.

🚀 Quick Start

1. Initialize the Project

Create a new folder and initialize a standard Vite React project, or simply manually create the files:

npm create vite@latest gap-analyzer -- --template react
cd gap-analyzer


2. Install Dependencies

Install the required packages (Tailwind CSS and Lucide Icons):

npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
npm install lucide-react


3. Configure Tailwind

Update your tailwind.config.js to look for your files:

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}


Add the Tailwind directives to your src/index.css:

@tailwind base;
@tailwind components;
@tailwind utilities;


4. Add Application Code

Replace the contents of src/App.jsx with the code provided in the App.jsx file.

Create a .env file in the root directory (next to package.json) and add your API key:

VITE_GROQ_API_KEY=gsk_your_key_here


5. Run Locally

Start the development server:

npm run dev


📄 Features

PDF Parsing: Uses pdf.js (loaded via CDN) to extract text from resumes.

AI Analysis: Uses Groq (Llama 3) to structure data.

PDF Generation: Uses jspdf (loaded via CDN) to create tailored resumes.