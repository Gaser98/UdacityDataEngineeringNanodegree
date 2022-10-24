import configparser
from datetime import datetime
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import udf, col
from pyspark.sql.functions import year, month, dayofmonth, hour, weekofyear, date_format


config = configparser.ConfigParser()
config.read('dl.cfg')

os.environ['AWS_ACCESS_KEY_ID']=config['AWS_ACCESS_KEY_ID']
os.environ['AWS_SECRET_ACCESS_KEY']=config['AWS_SECRET_ACCESS_KEY']


def create_spark_session():
    spark = SparkSession \
        .builder \
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:2.7.0") \
        .getOrCreate()
    return spark


def process_song_data(spark, input_data, output_data):
    """
        Description: This function loads song_data from S3 and processes it by extracting the songs and artist tables
        and then again loaded back to S3
        
        Parameters:
            spark       : Spark Session
            input_data  : location of song_data json files with the songs metadata
            output_data : S3 bucket were dimensional tables in parquet format will be stored
    """
    # get filepath to song data file
    song_data = input_data + 'song_data/*/*/*/*.json'
    song_schema = StructType([
        StructField("artist_id", StringType()),
        StructField("artist_latitude", DoubleType()),
        StructField("artist_location", StringType()),
        StructField("artist_longitude", StringType()),
        StructField("artist_name", StringType()),
        StructField("duration", DoubleType()),
        StructField("num_songs", IntegerType()),
        StructField("title", StringType()),
        StructField("year", IntegerType()),
    ])
    
    # read song data file
    df = spark.read.json(song_data, schema=songSchema)
    song_fields = ["title", "artist_id","year", "duration"]

    # extract columns to create songs table
    songs_table = df.select(song_fields).dropDuplicates().withColumn("song_id", monotonically_increasing_id())
    
    # write songs table to parquet files partitioned by year and artist
    songs_table.write.partitionBy("year", "artist_id").parquet(output_data + 'songs/')

    # extract columns to create artists table
    artists_table =["artist_id", "artist_name as name", "artist_location as location", "artist_latitude as latitude",        "artist_longitude as longitude"]
    
    # write artists table to parquet files
    artists_table.write.parquet(output_data + 'artists/')


def process_log_data(spark, input_data, output_data):
     """
     Description: This function loads log_data from S3 and processes it by extracting the songs and artist tables
        and then again loaded back to S3. Also output from previous function is used in by spark.read.json command
        
        Parameters:
            spark       : Spark Session
            input_data  : location of log_data json files with the events data
            output_data : S3 bucket were dimensional tables in parquet format will be stored
            
    """
    # get filepath to log data file
    log_data = "{}*/*/*events.json".format(input_data)

    # read log data file
    df = spark.read.json(log_data)
    
    # filter by actions for song plays
    df = df.filter(df.page == 'NextSong')
    users_fields = ["userdId as user_id", "firstName as first_name", "lastName as last_name", "gender", "level"]
    users_table = df.selectExpr(users_fields).dropDuplicates()

    users_table.write.parquet(output_data + 'users/')
    
    get_datetime = udf(date_convert, TimestampType())
    df = df.withColumn("start_time", get_datetime('ts'))

    time_table = df.select("start_time").dropDuplicates() \
        .withColumn("hour", hour(col("start_time")).withColumn("day", day(col("start_time")) \
        .withColumn("week", week(col("start_time")).withColumn("month", month(col("start_time")) \
        .withColumn("year", year(col("start_time")).withColumn("weekday", date_format(col("start_time"), 'E'))
    songs_table.write.partitionBy("year", "month").parquet(output_data + 'time/')

    df_songs = spark.read.parquet(output_data + 'songs/*/*/*')

    df_artists = spark.read.parquet(output_data + 'artists/*')
    
    # extract columns for users table    
    user_table = df.select(col("firstName"), col("lastName"), col("gender"), col("level"), col("userId")).distinct()
    
    # write users table to parquet files
     user_table.write.parquet("{}users/users_table.parquet".format(output_data))

    # create timestamp column from original timestamp column
    get_timestamp = udf(lambda x: datetime.fromtimestamp(x / 1000), TimestampType())
    df =  df.withColumn("timestamp", get_timestamp(col("ts")))
    
    # create datetime column from original timestamp column
    get_datetime = udf(lambda x: to_date(x), TimestampType())
    df = df.withColumn("start_time", get_timestamp(col("ts")))
    
    # extract columns to create time table
                    df = df.withColumn("hour", hour("timestamp"))
    df = df.withColumn("day", dayofmonth("timestamp"))
    df = df.withColumn("month", month("timestamp"))
    df = df.withColumn("year", year("timestamp"))
    df = df.withColumn("week", weekofyear("timestamp"))
    df = df.withColumn("weekday", dayofweek("timestamp"))

    time_table = df.select(col("start_time"), col("hour"), col("day"), col("week"), \
                           col("month"), col("year"), col("weekday")).distinct() 
    
    # write time table to parquet files partitioned by year and month
    time_table.write.partitionBy("year", "month").parquet("{}time/time_table.parquet".format(output_data))

    # read in song data to use for songplays table
    song_df = spark.sql("SELECT DISTINCT song_id, artist_id, artist_name FROM song_df_table"

    # extract columns from joined song and log datasets to create songplays table 
    songplays_table = df.join(song_df, song_df.artist_name == df.artist, "inner") \
        .distinct() \
        .select(col("start_time"), col("userId"), col("level"), col("sessionId"), \
                col("location"), col("userAgent"), col("song_id"), col("artist_id")) \
        .withColumn("songplay_id", monotonically_increasing_id())

    # write songplays table to parquet files partitioned by year and month
    songplays_table.write.partitionBy("year", "month") \
        .parquet("{}songplays/songplays_table.parquet".format(output_data))


def main():
    spark = create_spark_session()
    input_data = "s3a://udacity-dend/"
    output_data = ""
    
    process_song_data(spark, input_data, output_data)    
    process_log_data(spark, input_data, output_data)

if __name__ == "__main__":
    main()
