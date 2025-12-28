# Sample Queries for teadata-mcp

You can copy and paste these queries into ChatGPT to test the various tools provided by the `teadata-mcp` server.

## 🏢 Districts
*   "Show me information about Austin ISD."
*   "Tell me about the district Dallas ISD."
*   "What is the rating for Houston ISD?"
*   "Show details for district number 227901."

## 🏫 Campuses & Search
*   "Search for elementary schools in Austin."
*   "Find all charter schools in San Antonio."
*   "List private schools in Houston."
*   "Show me schools named 'Westlake'."

## 🔍 Campus Details
*   "Show me detailed information about Westlake High School."
*   "What are the demographics for Casis Elementary?"
*   "Tell me about the staffing and teacher salaries at Liberal Arts and Science Academy (LASA)."
*   "Where do students from Kealing Middle School transfer to?"

## 📍 Geographic / Radius Search
*   "Find schools within 5 miles of Westlake High School."
*   "Show me all schools within 3 miles of the coordinates 30.2672, -97.7431 (Austin City Hall)."
*   "What are the nearest charter schools to Bowie High School?"

## 📊 Comparison
*   "Compare Westlake High School and Lake Travis High School."
*   "Compare the demographics and teacher salaries of Austin High and McCallum High."
*   "Compare these three schools: IDEA Montopolis, KIPP Austin Collegiate, and LASA."

## 🔁 Transfer Insights
*   "Show transfer flows across Texas schools."
*   "Analyze transfer destinations in Austin ISD."
*   "What share of transfers go to charters vs traditional schools?"
*   "Do students transfer to higher-rated schools?"

## 🗺️ District Boundaries (Visual/Geographic)
*   "Which charter schools are located within the boundaries of Austin ISD?"
*   "Show me IDEA campuses inside the Houston ISD boundary."
*   "List charter campuses within Austin ISD boundaries (no map, just the table)."
*   "Map Austin ISD campuses colored by campus_2025_student_enrollment_economically_disadvantaged_percent and highlight charter schools; include demographic breakdowns."

## 🧭 Inspecting Fields / Follow-ups
*   "What geometry fields does Austin ISD expose for mapping?"
*   "Show details for IDEA Montopolis and include overall_rating_2025 and campus_2025_staff_teacher_student_ratio."
*   "List campuses in Austin ISD and include campus_2025_student_enrollment_english_learner_percent."
*   "Find charter campuses within Austin ISD boundaries on a map, then return a list with campus_2025_staff_teacher_student_ratio."
*   "Continue the previous boundary query using pagination.next_cursor."
*   "List charter campuses within Austin ISD boundaries using campus_list_format id_name, then show details for campus 227901001."
*   "Search campuses for 'IDEA' with include_total true and paginate using next_tool_call."
*   "List charter campuses within Austin ISD boundaries (table only), then export the full table to CSV."
*   "Load all remaining pages for the current campus list before summarizing."
