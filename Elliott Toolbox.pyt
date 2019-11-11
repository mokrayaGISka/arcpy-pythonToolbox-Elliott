import arcpy
arcpy.env.overwriteOutput = True ##Позволяем ArcToolbox перезаписывать существующие слои

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Toolbox"
        self.alias = ""

        # List of tool classes associated with this toolbox
        self.tools = [Tool]


class Tool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Elliott method"
        self.description = ""
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0=arcpy.Parameter(
            displayName = 'Input cities layer',
            name = 'city_feature',
            datatype = 'GPFeatureLayer',
            parameterType = 'Required',
            direction = 'Input')
        param1=arcpy.Parameter(
            displayName = 'Area center population',
            name = 'core_pop',
            datatype = 'GPLong',
            parameterType = 'Required',
            direction = 'Input')
        param2=arcpy.Parameter(
            displayName = 'Populations ratio',
            name = 'dif_pop',
            datatype = 'GPDouble',
            parameterType = 'Required',
            direction = 'Input')
        params = [param0,param1,param2]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        if parameters[0].value: ## Если переменная parameters[0].value существует (мы выбрали какой-то слой в первом поле), то...
        	parameters[1].enabled = True ## Делаем поле доступным для заполнения
        	parameters[2].enabled = True ## Делаем поле доступным для заполнения
        else:
        	parameters[1].enabled = False
        	parameters[2].enabled = False
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        #если первый параметр заполнен - получи список имён полей слоя. Если среди них нет поля "Population" - сообщи об этом
        if parameters[0].value:
			field_list_names = []
			for field in arcpy.ListFields(parameters[0].value):
				field_list_names.append(field.name)
			if "Population" not in field_list_names: #проверка наличия элемента "Population" среди элементов списка field_list_names
				parameters[0].setErrorMessage("No 'Population' field found. Create it")
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        #объявляем переменные
        cities = parameters[0].value
        mill = parameters[1].valueAsText
        koeff = parameters[2].valueAsText.replace(",",".") #заменяем запятую на точку в переменной koeff с помощью replace. Это нужно, чтобы тулбокс корректно воспринял десятичную дробь.

        ## МОДЕЛИРОВАНИЕ ЗОН ВЛИЯНИЯ ГОРОДОВ ПО МЕТОДУ ЭЛЛИОТА		
        cities = arcpy.mapping.Layer(parameters[0].valueAsText) ##Пока что parameters[0].valueAsText - это геопроцессинговый объект. Некоторые операции, например выборка по атрибутам возможна в ArcToolbox только для слоёв. Поэтому необходимо превратить объект в слой с помощью arcpy.mapping.Layer
        arcpy.AddXY_management(cities) ##Поулчили координаты городов слоя Ukranian_Cities      
        arcpy.CopyFeatures_management(cities, 'in_memory/layer1') ##Cкопировали Ukranian_Cities в in_memory/layer1
        layer1 = arcpy.mapping.Layer('in_memory/layer1') ##Аналогично cities превращаем объект 'in_memory/layer1' в слой
        chislo = int(arcpy.GetCount_management(cities).getOutput(0)) ##Получили число объектов в слое с городами. Оно нам понадобится, чтобы по очереди выбирать города и производить с ними набор действий
        arcpy.AddMessage("The number of cities in your layer :"+str(chislo)) ##Вывели на экран число объектов слоя с городами, чтобы понимать масштаб работ
        ## Записали населения городов в список
        pops=[]
        for row in arcpy.da.SearchCursor(cities,["Population"]):
        	pops.append(row[0])
        ## Идея в том, чтобы в одной таблице атрибутов получить FID города и FID города, к которому тяготеет данный. А потом попарно их соединить линиями.
        ## Выбрать точку из слоя по FID, найти ближайшего соседа и вытащить FID ближайшего соседа. Предполагается, что все города меньше 1 000 000 чел.
        nearfids=[] ## Список с FID городов, к которым тяготеют данные
        for x in range(chislo):
        	if pops[x]>=int(mill):
        		nearfids.append(x+1) ##Если население города больше 1 млн чел., то он является центром зоны и ни к кому не тяготеет. Поэтому в nearfids запишем его же FID (как будто он тяготеет к самому себе). x+1 потому что в скопированном слое нумерация начинается не с 0, а с 1, поэтому FID как бы съезжают на 1
        	else:
        		arcpy.SelectLayerByAttribute_management(cities,"NEW_SELECTION",""" "FID"=%i"""%(x)) ##Выбираем город по FID. Вместо %i подставляем x. Поскольку после % идёт буква i, то подставляемый вмесо неё элемент будет типа Integer
        		treshold = float(koeff)*int(pops[x]) ##Вычисляем минимальную людность города, к которому может тяготеть данный
        		arcpy.SelectLayerByAttribute_management(layer1,"NEW_SELECTION",""" "Population">=%i"""%(treshold)) ##Выбираем все города с людностью больше или равной той, что мы вычислили
        		arcpy.Near_analysis(cities,layer1,"#","NO_LOCATION","NO_ANGLE") ##Из выделенных городов выбираем ближайшего соседа данного.
        		for row in arcpy.da.SearchCursor(cities, "NEAR_FID"):
        			nearfids.append(row[0]) ##Считываем FID полученного ближайшего соседа и добавляем его в список
        	if x%25==0: ##Здесь мы проверяем делимость переменной x на 25 при помощи значка %. Если остаток от деления 0 - то мы выводим сообщение. Таким образом мы отслеживаем прогресс работы инструмента, но не печатаем каждый элемент, а лишь каждый 25-й, чтоб не захламлять экран тулбокса.
				arcpy.AddMessage("I've done %s cities"%(x))
        ## Снимаем выделение со слоёв
        arcpy.SelectLayerByAttribute_management(cities,"CLEAR_SELECTION")
        arcpy.SelectLayerByAttribute_management(layer1,"CLEAR_SELECTION")
        ## Создаём колонку, в которую будем записывать near fid. За одно снесём ненужную нам колонку 'NEAR_FID'
        arcpy.DeleteField_management(cities,'NEAR_FID')
        arcpy.AddField_management(cities,"Near_FID","SHORT")
        ## В созданную колонку слоя с городами по очереди записываем элементы nearfids. Таким образом, в таблице атрибутов имеем FID самого города и FID города, к которому он тяготеет. Центры зон тяготеют сами к себе
        i=0
        ucurs = arcpy.da.UpdateCursor(cities,["Near_FID"])
        for row in ucurs:
        	row[0]=nearfids[i]
        	##arcpy.AddMessage(nearfids[i])
        	ucurs.updateRow(row)
        	i=i+1
        ## Координаты самих городов у нас уже есть в колонках POINT_X и POINT_Y. А вот координаты ближайших соседей - нет. 
        ## К таблице cities привязываем таблицу layer1. В качестве связующих полей выступают "Near_FID" из cities и "FID" из Destinations.
        arcpy.JoinField_management(cities,'Near_FID',layer1,'FID')
        ## После того, как таблицы связаны, копируем таблицу атрибутов, в котором прошла связь - cities. 
        arcpy.CopyRows_management(cities, 'in_memory/layer2')
        ## Теперь, имея координаты городов и их ближайших соседей, можно прорисовать линии между ними, обозначив таким образом графически, кто к кому тяготеет.
        ## Но для начала получим объект описания слоя cities и узнаем, в какой папке он лежит у пользователя. В эту же папку мы положим выходной слой с линиями.
        desc = arcpy.Describe(cities)
        path = desc.path
        arcpy.XYToLine_management('in_memory/layer2',path+"/lines","POINT_X","POINT_Y","POINT_X_1","POINT_Y_1","GEODESIC")
        ## После работы в слое с городами у нас остались ненужные поля. Удалим их
        arcpy.DeleteField_management(cities, ['POINT_X', 'POINT_Y', 'NEAR_DIST', 'Near_FID', 'Name_1', 'Populati_1', 'POINT_X_1', 'POINT_Y_1'])
        return