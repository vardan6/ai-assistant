Please review the document: /home/vardana/proj/aregi/ai-assistant/docs/solar_interview_task.md 
	You can read a few lines from each data file to understand its formatting if needed and the type and amount of information those files are providing if you need. But Please be careful: files are large. 
	Please carefully read the section: "What the assistant must handle". 
	With this request now I would like to work with you to have a very very very good test coverage right now for the plan of the prompts we want to define for testing the application.
		It separates three types of prompts. Current states, statistics, and anomaly lookup. 
		Definitely the prompts listed there should be included in our plan. But also I think we need to come up with much much better and much much fuller coverage for the prompts and expected answers. 
		But first let's concentrate on prompts. I need very good examples for each case. 
			Case is plans, inverters, generation readings, weather, alerts, maintenance, tickets, anomalies. For all of those types I want very good test coverage. 
			By test I mean a case. description what we request, what we expect.

While trying to discover and define cases for testing, I need you to think about the tables where we specify children and/or their parents. When a query or question is asked in the chat, it may assume multiple iterations over an agentic loop or multiple tool calls. A tool call chain should be assumed so we ask for something related to some other thing. A tool call chain should be somehow orchestrated. What is the better and the best approach for that? Can we do prior tool chain orchestration for all the cases according to data relationship or is this something that the LLM can do during the agent work? Or what can we do prior to the LLM agent work to enhance and simplify this relationship, to make it easier and more reliable, to be able to create this chain tool, called chain, to finally be able to obtain the final data? 



One very important thing to notice is we want to get the current status and there are questions about containing right now. The expression right now, but the data is old and right now doesn't much. What can you suggest with this? 

Please review the document: /home/vardana/proj/aregi/ai-assistant/docs/solar_interview_task.md 
	You can read a few lines from each data file to understand its formatting if needed and the type and amount of information those files are providing if you need. But Please be careful: files are large. 
	Please carefully read the section: "What the assistant must handle". 
	As the first iteration I would like to hear your suggestions: what type of information else can be obtained? What approaches and solutions? Right now I am thinking of a strategy for how to structure the tools so the AI agent can very efficiently, using those tools, obtain whatever information the user is trying to get. 
	
One very important thing to notice is we want to get the current status and there are questions about containing right now. The expression right now, but the data is old and right now doesn't much. What can you suggest with this? 







Please review the document: /home/vardana/proj/aregi/ai-assistant/docs/solar_interview_task.md 
We have done some initial data analysis which is stored here: docs/dataset-analysis.md, which is done by the newly implemented script: /home/vardana/proj/aregi/ai-assistant/scripts/profile_dataset.py

Let's create a test plan document. And first content, please do:
First of all extract all the test cases from the initial task document: docs/solar_interview_task.md 


----
Now read the file: /home/vardana/proj/aregi/ai-assistant/docs/dataset-analysis.md Understand data and their correlation. Understand what data have a relation to others, Understand what are children data of others. Understand what are parents of others. Do we need or how to somehow store a better graph which can be somehow used for implementing AI agents' work in AI agents' re-act loop or link a graph loop so it can, according to the graph, understand or define its next step? For example when some question or prompt is asked, it needs to first be able to define the chain of tools which it can or should call to achieve its target information or value. Do we need a graph to help an AI agent for reliable work? Also we have several tables there which are mappings or resolvers where we resolve some, for example, column name from the more readable names. Read all the sections in that document and try to understand what can be used during active Agents runtime work and how it should be represented and attached to the Agents' work context so it can simplify and increase the output quality.


Please read the below instruction from the initial task description from: docs/solar_interview_task.md 
4. Aggregation in code
The LLM must not be asked to count rows or sum columns from raw CSV text — that is slow, expensive, and unreliable. Aggregations must happen in code (Python, SQL, pandas, etc.) before the result is passed to the LLM for interpretation.

So as I can right now understand and plan, we have to have all the tools to aggregate and calculate different types of mathematical outcomes. For example:
- Summary
- Count
- Numbers
What other mathematical operations can be done? For example:
- mean
- median
- average
- rms

Different types of mathematical functions that can be asked to calculate over some range of some data. Range may be mentioned by date or by count, starting from date. I need all kinds of tools and all kinds of cases for this so later we can implement very good tool coverage to cover all the prompts.
Or one other approach is to come up with very trivial very basic tools which will eventually cover all the necessary answers. AI agent, which we implement cleverly, will sequentially indicate, solve, and create a chain of tool executions, then execute and then calculate and get the final target values or answers or multiple values. The last steps are not summarized but gathered together by preparing an answer by the LLM. 

	Please carefully read the section: "What the assistant must handle". 
	With this request now I would like to work with you to have a very very very good test coverage right now for the plan of the prompts we want to define for testing the application.
		It separates three types of prompts. Current states, statistics, and anomaly lookup. 
		Definitely the prompts listed there should be included in our plan. But also I think we need to come up with much much better and much much fuller coverage for the prompts and expected answers. 
		But first let's concentrate on prompts. I need very good examples for each case. 
			Case is plans, inverters, generation readings, weather, alerts, maintenance, tickets, anomalies. For all of those types I want very good test coverage. 
			By test I mean a case. description what we request, what we expect.

While trying to discover and define cases for testing, I need you to think about the tables where we specify children and/or their parents. When a query or question is asked in the chat, it may assume multiple iterations over an agentic loop or multiple tool calls. A tool call chain should be assumed so we ask for something related to some other thing. A tool call chain should be somehow orchestrated. What is the better and the best approach for that? Can we do prior tool chain orchestration for all the cases according to data relationship or is this something that the LLM can do during the agent work? Or what can we do prior to the LLM agent work to enhance and simplify this relationship, to make it easier and more reliable, to be able to create this chain tool, called chain, to finally be able to obtain the final data?

Sorry if I repeat myself. I'm trying to understand what and how some data can be attached to the context so it better finds the relationship between tools. What tools are really necessary to work with data sets? I'm even not sure where to start from. Start from designing tools or start from defining test cases and then define tools. I even don't know where to start. Assuming we start from tools which just give some things from datasets, maybe it's better to start from test case descriptions, like target what we want to achieve. I am not sure. Please, please read this and suggest better direction. Some tools are already implemented but because I haven't reviewed tools yet, we can completely rewrite it so we don't assume that it's already good quality. It may be the best quality already. We should be very careful about removing but also we should not fix on them as a working version and not remove them if we have a clearly good approach. So maybe the first thing we can do is understand and list all the data and understand the relationships between the data. It's mentioned as children and parent. Understand when we do ask prompts in human language It should be converted to the corresponding value in the data sets which are under columns and rows. Or there can be some mathematical operations: sums, averages, medians, outliers. All the cases should be covered especially which is asked for directly. But also according to dataset types, the data types, each data type assumes what values a user can ask for. There should be some generic data values which are commonly asked for data types like that. This is another thing to consider and look at separately. And I want to understand and build each and every combination. This combination can be deep. It should cause the agent to create chains of command executions, chains of tool executions to call `getAnswer`, until it finds the final answer. Somehow I believe it has to have some graph or some schema where it can find the interrelation till the answer So it uses that schema that interrelates data to build the chain of executions of tools We need somehow to plant this. Again I may be repeating but you mentioned somewhere that when we have a name mapping or name-to-column-name mapping, we will simplify, increase quality, and reduce answer risk. You mentioned some terms I want to remember: to highly increase output quality, building the output chain, building the against-tool call chain. Another question, which is less important right now: from this chain it should somehow understand which tools can be called in parallel. For example, call tools then call the LLM. Before calling LLM, obtain outputs from multiple tools and then pass them to the fourth tool, etc. 
