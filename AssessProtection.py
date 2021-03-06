# -*- coding: utf-8 -*-
"""
Created on Thu Aug 10 10:28:29 2017 by nmtarr

Description:  Produces results related to the protection of ecological systems
and species.  Note that some processes (lines 33-35) take up to an hour to run
and could be skipped if the floodPAD layer already exists. Also note that this
code queries the Analytic Databse.

This code may have some reduncancy in it that could be cleaned up, and it may
needs some more documentation.
"""
import sys, matplotlib.pyplot as plt
sys.path.append('P:/Proj3/USGap/Scripts/SE_Woody_Wetlands')
execfile("T:/Scripts/AppendPaths27.py")
execfile("T:/Scripts/AppendGAPAnalysis.py")
import gapanalysis as ga
import gapproduction as gp
import SEWWConfig as floodconfig
import gapconfig as config
import pandas as pd
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 10)
pd.set_option('display.width', 1000)

###### Geoprocessing environment settings
import arcpy
arcpy.ResetEnvironments()
arcpy.CheckOutExtension("Spatial")
arcpy.env.overwriteOutput=True
arcpy.env.extent = "MAXOF" 
arcpy.env.pyramid = 'PYRAMIDS'
arcpy.env.snapRaster = config.CONUS_extent
arcpy.env.rasterStatistics = "STATISTICS"
arcpy.env.cellSize = 30

##################################  How much of SEWW is protected?
###############################################################################
'''  # Commented out to keep graph-making and slow data producing separate.
PAD = arcpy.Raster(floodconfig.PADUS_Man)
FloodBin = arcpy.Raster(floodconfig.resultDir + "SEWW.tif")

# Overlay the PAD layer and binary SEWW layer
floodPAD = PAD * (FloodBin - 9)
floodPAD.save(floodconfig.resultDir + "SEWWPAD.tif")
'''
# Make a pie chart of protection
floodPADRAT = ga.misc.RATtoDataFrame(floodconfig.resultDir + "SEWWPAD.tif")
ax = floodPADRAT.plot(y="cell_count", kind='Pie', figsize=(4,4), autopct='%.2f',
                 legend=False,
                 colors = ["#009933", "#cccc00", "#999999", "#e6e6e6"])
ax.set_ylabel("%")
fig = plt.gcf()
fig.savefig(floodconfig.resultDir + "Flooplain protection.png", dpi=600,
            bbox_inches="tight")

############################## How much of each SEWW system is protected?
###############################################################################
def getEcoSysProtection(ecoSys):
    '''
    (string, list) -> pandas DataFrame
    
    Description:
    A function that returns the percentage of an ecological system
        that is in the GAP PAD statuses of interest.
    
    Argument:
    ecoSys -- The name of the ecological system that you are interested in.
    '''
    blank = pd.DataFrame(index = ["1","2","3","4", "1234"], 
                         columns=["cells", "percent"])
    try:
        # Connect to analytic database
        anCur, anCon = gp.gapdb.ConnectAnalyticDB()
        
        sql = """
        --Retrieve ecological system boundary info for one system.
        WITH ESPAD AS (
        SELECT lu_boundary_gap_landfire.boundary, lu_boundary_gap_landfire.count,
               lu_boundary_gap_landfire.gap_landfire, lu_boundary.value, lu_boundary.padus1_4, 
               padus1_4.revoid, padus1_4.gap_sts
        FROM lu_boundary_gap_landfire 
        INNER JOIN lu_boundary ON lu_boundary.value = lu_boundary_gap_landfire.boundary
        INNER JOIN padus1_4 ON lu_boundary.padus1_4 = padus1_4.revoid),
        
        --Retrieve ecological system name and code
        ECOSYS AS (
        SELECT g.ecosys_lu, g.value
        FROM gap_landfire as g
        WHERE g.ecosys_lu = '{0}')
        
        --Group records from joined data views by count
        SELECT ESPAD.gap_sts, sum(ESPAD.count) AS cells
        FROM ECOSYS INNER JOIN ESPAD ON ECOSYS.value = ESPAD.gap_landfire
        GROUP BY ESPAD.gap_sts
        """.format(ecoSys)
        
        qryDF = pd.read_sql(sql, anCon).set_index("gap_sts")
        qryDF.loc["1234", "cells"] = sum(qryDF.cells)
        qryDF["percent"] = [100*(qryDF.loc[i, "cells"]/qryDF.loc["1234", "cells"]) for i in qryDF.index]
        
        del anCur
        anCon.close()
        
        for x in qryDF.index:
            blank.loc[x, "cells"] = qryDF.loc[x, "cells"]
            blank.loc[x, "percent"] = qryDF.loc[x, "percent"]
            blank.fillna(0, inplace=True)
        return blank
    except Exception as e:
        print(e)

floodSysDF = pd.read_csv(floodconfig.SEWWSystemCSV)
floodSysDF = floodSysDF[floodSysDF.include == 1]
floodSysDF.drop(["include"], inplace=True, axis=1)
floodSysDF["protected1&2(%)"] = [sum(getEcoSysProtection(i).iloc[:2].percent) for i in floodSysDF.system_name]
floodSysDF.to_csv(floodconfig.resultDir + "EcolSysProtection.csv")

###############################################  Protection of species' habitat
###############################################################################
# Function to return protection status of a species.
def getProtection(strUC, season):
    '''
    (string, string) -> pandas DataFrame
    
    Description:
    A function that returns the amount of a species' habitat that is in status
    1, 2, 3, and 4 lands by season.
    
    Arguments:
    strUC -- Species code (e.g., "mVASHx")
    season -- Season to summarize on (i.e., summer, winter, or all year)
    '''
    try:
        seasonDict = {"summer":(1,3), "winter":(2,3), "all year":(3,3)}
        
        # Connect to analytic database
        anCur, anCon = gp.gapdb.ConnectAnalyticDB()
        
        sql = """
        --Retrieve species boundary info for one species.
        WITH SpPAD AS (
        SELECT lu_boundary_species.boundary, lu_boundary_species.count, 
               lu_boundary_species.season, lu_boundary_species.species_cd, 
               lu_boundary.value, lu_boundary.padus1_4, padus1_4.revoid, 
               padus1_4.gap_sts
        FROM lu_boundary_species 
        INNER JOIN lu_boundary ON lu_boundary.value = lu_boundary_species.boundary
        INNER JOIN padus1_4 ON lu_boundary.padus1_4 = padus1_4.revoid
        WHERE (lu_boundary_species.species_cd = '{0}' 
               and (lu_boundary_species.season = {1} or lu_boundary_species.season = {2})))
        
        
        --Group by count
        SELECT  s.gap_sts, sum(s.count) AS cells
        FROM SpPAD AS s
        GROUP BY s.gap_sts
        """.format(strUC, str(seasonDict[season][0]), str(seasonDict[season][1]))
        
        qryDF = pd.read_sql(sql, anCon).set_index("gap_sts")
        
        if len(qryDF) == 0:
            qryDF = pd.DataFrame(data=[0,0,0,0], index=[1,2,3,4], columns=["cells"])
            qryDF.index.name = 'gap_sts'
        
        del anCur
        anCon.close()
        
        return qryDF
    except Exception as e:
        print(e)
        print(strUC)

# Get list of species to query.
summerDF = pd.read_csv(floodconfig.summerTopSpList)
summerSp = list(summerDF.strUC)
winterDF = pd.read_csv(floodconfig.winterTopSpList)
winterSp = list(winterDF.strUC)

# Empty dataframes to fill out.
summer0 = pd.DataFrame(index=summerSp, 
                       columns=["status_1", "status_2", "status_3", "status_4"])
winter0 = pd.DataFrame(index=winterSp, 
                       columns=["status_1", "status_2", "status_3", "status_4"])

#### Fill out summer DF
print("\n*** SUMMER ***")
for sp in summerSp:
    prot = getProtection(sp, season="summer")
    try:
        summer0.loc[sp, 'status_1'] = int(prot.loc["1"])
    except: 
        summer0.loc[sp, 'status_1'] = 0
    try:
        summer0.loc[sp, 'status_2'] = int(prot.loc["2"])
    except:
        summer0.loc[sp, 'status_2'] = 0
    try:
        summer0.loc[sp, 'status_3'] = int(prot.loc["3"])
    except:
        summer0.loc[sp, 'status_3'] = 0
    try:
        summer0.loc[sp, 'status_4'] = int(prot.loc["4"])
    except:
        summer0.loc[sp, 'status_4'] = 0
summer0["total_cells"] = summer0.status_1 + summer0.status_2 + summer0.status_3 + summer0.status_4
summer0['status_1%'] = 100.*summer0.status_1/summer0.total_cells
summer0['status_2%'] = 100.*summer0.status_2/summer0.total_cells
summer0['status_3%'] = 100.*summer0.status_3/summer0.total_cells
summer0['status_4%'] = 100.*summer0.status_4/summer0.total_cells

# Summer protection description
summer1 = summer0.apply(pd.to_numeric)
summer1.to_csv(floodconfig.resultDir + "Summer protection.csv")
summerProtDesc = summer1.describe()
print(summerProtDesc)
summerProtDesc.to_csv(floodconfig.resultDir + "Summer protection descriptive stats.csv")
    
# Graph protection
dropCols = ["status_1", "status_2", "status_3", "status_4", "total_cells"]
# Summer
summer2 = summer1.drop(dropCols, axis=1)
summer2.rename(columns={"status_1%":"1", "status_2%":"2","status_3%":"3",
                        "status_4%":"4",}, inplace=True)
sumAx = summer2.plot(kind="box", title="Summer", yticks=range(0,100,10),
                     figsize=(5,4))
sumAx.set_ylabel("Percent of Species' Total Habitat Area")
sumAx.set_xlabel("GAP Protection Status")
fig = plt.gcf()
fig.savefig(floodconfig.resultDir + "Protection Boxplot Summer.png", dpi=600,
            bbox_inches="tight")

#### Fill out winter DF
print("\n*** WINTER ***")
for sp in winterSp:
    prot = getProtection(sp, season="winter")
    try:
        winter0.loc[sp, 'status_1'] = int(prot.loc["1"])
    except: 
        winter0.loc[sp, 'status_1'] = 0
    try:
        winter0.loc[sp, 'status_2'] = int(prot.loc["2"])
    except:
        winter0.loc[sp, 'status_2'] = 0
    try:
        winter0.loc[sp, 'status_3'] = int(prot.loc["3"])
    except:
        winter0.loc[sp, 'status_3'] = 0
    try:
        winter0.loc[sp, 'status_4'] = int(prot.loc["4"])
    except:
        winter0.loc[sp, 'status_4'] = 0
        
winter0["total_cells"] = winter0.status_1 + winter0.status_2 + winter0.status_3 + winter0.status_4
winter0['status_1%'] = 100.*winter0.status_1/winter0.total_cells
winter0['status_2%'] = 100.*winter0.status_2/winter0.total_cells
winter0['status_3%'] = 100.*winter0.status_3/winter0.total_cells
winter0['status_4%'] = 100.*winter0.status_4/winter0.total_cells

# Winter protection description
winter1 = winter0.apply(pd.to_numeric)
winter1.to_csv(floodconfig.resultDir + "Winter protection.csv")
winterProtDesc = winter1.describe()
print(winterProtDesc)
winterProtDesc.to_csv(floodconfig.resultDir + "Winter protection descriptive stats.csv")

# Winter
winter2 = winter1.drop(dropCols, axis=1)
winter2.rename(columns={"status_1%":"1", "status_2%":"2","status_3%":"3",
                        "status_4%":"4",}, inplace=True)
wintAx = winter2.plot(kind="box", title="Winter", yticks=range(0,100,10),
                      figsize=(5,4))
wintAx.set_ylabel("Percent of Species' Total Habitat Area")
wintAx.set_xlabel("GAP Protection Status")
fig = plt.gcf()
fig.savefig(floodconfig.resultDir + "Protection Boxplot Winter.png", dpi=600,
            bbox_inches="tight")

#######################  Make table of status 1 or 2 protection for top species
###############################################################################
# get combined species list
tops = set(summerSp) | set(winterSp)

# Define function to find out how much habitat is in status 1 or 2
def status1or2(strUC, season):
    '''
    (string, string) -> float
    
    Description:
        Determines what percentage of species's seasonal habitat is in status
    1 or 2.
    '''
    # Blank DataFrame to fill out
    blank = pd.DataFrame(index = ["1","2","3","4"],
                         columns=["cells", "percent"])
    # Get the protection amounts from Analytic DB
    one = getProtection(strUC, season)
    # Fill out the blank table, use this blank so that errors don't occur
    # if a species' habitat is all in less than 4 statuses.
    for x in one.index:
            blank.loc[x, "cells"] = one.loc[x, "cells"]
            blank.fillna(0, inplace=True)
    # get total count and calculate the percentage in 1 or 2 status.
    total = float(blank.cells.sum())
    protDF = blank.iloc[:2]
    protCells = protDF.cells.sum()
    return 100*(protCells/total)
  
# Fill out a DataFrame
df10 = pd.DataFrame(index=tops, columns=["summer", "winter"])
df10["common_name"] = [gp.gapdb.NameCommon(s) for s in df10.index]
df10["summer"] = [status1or2(strUC, "summer") for strUC in df10.index]
df10["winter"] = [status1or2(strUC, "winter") for strUC in df10.index]
df10.fillna(0, inplace=True)
df10.to_csv(floodconfig.resultDir + "TopSpeciesProtection1or2.csv")